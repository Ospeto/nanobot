"""Agent loop: the core processing engine."""

from __future__ import annotations

import asyncio
import json
import re
from contextlib import AsyncExitStack
from pathlib import Path
from typing import TYPE_CHECKING, Awaitable, Callable

import json_repair
from loguru import logger

from nanobot.agent.context import ContextBuilder
from nanobot.agent.memory import MemoryStore
from nanobot.agent.subagent import SubagentManager
from nanobot.agent.tools.cron import CronTool
from nanobot.agent.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from nanobot.agent.tools.message import MessageTool
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.shell import ExecTool
from nanobot.agent.tools.spawn import SpawnTool
from nanobot.agent.tools.web import WebFetchTool, WebSearchTool
from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMProvider
from nanobot.session.manager import Session, SessionManager

if TYPE_CHECKING:
    from nanobot.config.schema import ExecToolConfig
    from nanobot.cron.service import CronService


class AgentLoop:
    """
    The agent loop is the core processing engine.

    It:
    1. Receives messages from the bus
    2. Builds context with history, memory, skills
    3. Calls the LLM
    4. Executes tool calls
    5. Sends responses back
    """

    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        max_iterations: int = 20,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        memory_window: int = 50,
        brave_api_key: str | None = None,
        exec_config: ExecToolConfig | None = None,
        cron_service: CronService | None = None,
        restrict_to_workspace: bool = False,
        session_manager: SessionManager | None = None,
        mcp_servers: dict | None = None,
    ):
        from nanobot.config.schema import ExecToolConfig
        self.bus = bus
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.memory_window = memory_window
        self.brave_api_key = brave_api_key
        self.exec_config = exec_config or ExecToolConfig()
        self.cron_service = cron_service
        self.restrict_to_workspace = restrict_to_workspace

        self.context = ContextBuilder(workspace)
        self.sessions = session_manager or SessionManager(workspace)
        self.tools = ToolRegistry()
        self.subagents = SubagentManager(
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            brave_api_key=brave_api_key,
            exec_config=self.exec_config,
            restrict_to_workspace=restrict_to_workspace,
        )

        self._running = False
        self._mcp_servers = mcp_servers or {}
        self._mcp_stack: AsyncExitStack | None = None
        self._mcp_connected = False
        self._mcp_connecting = False
        self._consolidating: set[str] = set()  # Session keys with consolidation in progress
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        # File tools (workspace for relative paths, restrict if configured)
        allowed_dir = self.workspace if self.restrict_to_workspace else None
        self.tools.register(ReadFileTool(workspace=self.workspace, allowed_dir=allowed_dir))
        self.tools.register(WriteFileTool(workspace=self.workspace, allowed_dir=allowed_dir))
        self.tools.register(EditFileTool(workspace=self.workspace, allowed_dir=allowed_dir))
        self.tools.register(ListDirTool(workspace=self.workspace, allowed_dir=allowed_dir))

        # Shell tool
        self.tools.register(ExecTool(
            working_dir=str(self.workspace),
            timeout=self.exec_config.timeout,
            restrict_to_workspace=self.restrict_to_workspace,
        ))

        # Web tools
        self.tools.register(WebSearchTool(api_key=self.brave_api_key))
        self.tools.register(WebFetchTool())

        # Message tool
        message_tool = MessageTool(send_callback=self.bus.publish_outbound)
        self.tools.register(message_tool)

        # Spawn tool (for subagents)
        spawn_tool = SpawnTool(manager=self.subagents)
        self.tools.register(spawn_tool)

        # Cron tool (for scheduling)
        if self.cron_service:
            self.tools.register(CronTool(self.cron_service))

        # MCP Installer tools
        from nanobot.agent.tools.mcp_registry import SearchMCPRegistryTool
        from nanobot.agent.tools.install_skill import InstallSkillTool
        self.tools.register(SearchMCPRegistryTool())
        self.tools.register(InstallSkillTool())

        # Game tools (for Digimon companion)
        try:
            from nanobot.agent.tools.init import InitDigimonTool
            from nanobot.agent.tools.calendar import BlockTimeTool, ListCalendarTool, ManageCalendarTool
            from nanobot.agent.tools.study import SyncStudyResourcesTool, AnalyzeStudyScheduleTool
            
            self.tools.register(FeedTool())
            self.tools.register(HealTool())
            self.tools.register(PlayTool())
            self.tools.register(ListTasksTool())
            self.tools.register(CompleteTaskTool())
            self.tools.register(AddAssignmentTool())
            self.tools.register(ManageMemoryGraphTool())
            self.tools.register(SearchMemoryGraphTool())
            self.tools.register(InitDigimonTool())
            self.tools.register(BlockTimeTool())
            self.tools.register(ListCalendarTool())
            self.tools.register(ManageCalendarTool())
            self.tools.register(SyncStudyResourcesTool())
            self.tools.register(AnalyzeStudyScheduleTool())
        except ImportError as e:
            logger.error(f"Failed to import game tools: {e}")
    async def _connect_mcp(self) -> None:
        """Connect to configured MCP servers (one-time, lazy)."""
        if self._mcp_connected or self._mcp_connecting or not self._mcp_servers:
            return
        self._mcp_connecting = True
        from nanobot.agent.tools.mcp import connect_mcp_servers
        try:
            self._mcp_stack = AsyncExitStack()
            await self._mcp_stack.__aenter__()
            await connect_mcp_servers(self._mcp_servers, self.tools, self._mcp_stack)
            self._mcp_connected = True
        except Exception as e:
            logger.error("Failed to connect MCP servers (will retry next message): {}", e)
            if self._mcp_stack:
                try:
                    await self._mcp_stack.aclose()
                except Exception:
                    pass
                self._mcp_stack = None
        finally:
            self._mcp_connecting = False

    def _set_tool_context(self, channel: str, chat_id: str, message_id: str | None = None) -> None:
        """Update context for all tools that need routing info."""
        if message_tool := self.tools.get("message"):
            if isinstance(message_tool, MessageTool):
                message_tool.set_context(channel, chat_id, message_id)

        if spawn_tool := self.tools.get("spawn"):
            if isinstance(spawn_tool, SpawnTool):
                spawn_tool.set_context(channel, chat_id)

        if cron_tool := self.tools.get("cron"):
            if isinstance(cron_tool, CronTool):
                cron_tool.set_context(channel, chat_id)

    @staticmethod
    def _strip_think(text: str | None) -> str | None:
        """Remove <think>…</think> blocks that some models embed in content."""
        if not text:
            return None
        return re.sub(r"<think>[\s\S]*?</think>", "", text).strip() or None

    @staticmethod
    def _tool_hint(tool_calls: list) -> str:
        """Format tool calls as concise hint, e.g. 'web_search("query")'."""
        def _fmt(tc):
            val = next(iter(tc.arguments.values()), None) if tc.arguments else None
            if not isinstance(val, str):
                return tc.name
            return f'{tc.name}("{val[:40]}…")' if len(val) > 40 else f'{tc.name}("{val}")'
        return ", ".join(_fmt(tc) for tc in tool_calls)

    async def _run_agent_loop(
        self,
        initial_messages: list[dict],
        on_progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> tuple[str | None, list[str]]:
        """
        Run the agent iteration loop.

        Args:
            initial_messages: Starting messages for the LLM conversation.
            on_progress: Optional callback to push intermediate content to the user.

        Returns:
            Tuple of (final_content, list_of_tools_used).
        """
        messages = initial_messages
        iteration = 0
        final_content = None
        tools_used: list[str] = []
        text_only_retried = False

        while iteration < min(self.max_iterations, 5): # STRICT COST GUARDRAIL
            iteration += 1

            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            if response.has_tool_calls:
                if on_progress:
                    clean = self._strip_think(response.content)
                    if clean:
                        await on_progress(clean)
                    await on_progress(self._tool_hint(response.tool_calls))

                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments, ensure_ascii=False)
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts,
                    reasoning_content=response.reasoning_content,
                )

                for tool_call in response.tool_calls:
                    tools_used.append(tool_call.name)
                    args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                    logger.info("Tool call: {}({})", tool_call.name, args_str[:200])
                    result = await self.tools.execute(tool_call.name, tool_call.arguments)
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )
            else:
                final_content = self._strip_think(response.content)
                # Some models send an interim text response before tool calls.
                # Give them one retry; don't forward the text to avoid duplicates.
                if not tools_used and not text_only_retried and final_content:
                    text_only_retried = True
                    logger.debug("Interim text response (no tools used yet), retrying: {}", final_content[:80])
                    final_content = None
                    continue
                break

        return final_content, tools_used

    async def _proactive_mas_alerts_loop(self):
        """Background task to poll MAS Dashboard and trigger LLM alerts."""
        while self._running:
            try:
                # Give the agent a few seconds to start up fully
                await asyncio.sleep(10)
                
                # 1. Look for an active telegram session
                sessions = self.sessions.list_sessions()
                tg_session = next((s for s in sessions if s["key"].startswith("telegram:")), None)
                if not tg_session:
                    await asyncio.sleep(300)
                    continue
                    
                channel, chat_id = tg_session["key"].split(":", 1)
                
                # 2. Check Notion
                from nanobot.game.notion_api import NotionIntegration
                from nanobot.game.database import SessionLocal
                from nanobot.game import models
                from datetime import datetime, timezone
                
                notion = NotionIntegration()
                if not notion.is_authenticated():
                    await asyncio.sleep(3600)
                    continue
                    
                tasks = await asyncio.to_thread(notion.fetch_mas_deadlines)
                
                def _check_and_mark_mas_alert(tid: str, title: str, task_type: str) -> bool:
                    db = SessionLocal()
                    try:
                        state = db.query(models.TaskSyncState).filter_by(id=tid).first()
                        if not state:
                            state = models.TaskSyncState(id=tid, source="notion", title=title, status="pending", task_type=task_type)
                            db.add(state)
                            
                        skip = False
                        if state.last_notified_at:
                            try:
                                last = datetime.fromisoformat(state.last_notified_at)
                                if (datetime.utcnow() - last).total_seconds() < 86400: # 1 msg per day
                                    skip = True
                            except Exception:
                                pass
                                
                        if not skip:
                            state.last_notified_at = datetime.utcnow().isoformat()
                            db.commit()
                            return True
                        return False
                    finally:
                        db.close()
                
                for t in tasks:
                    if not t["due_date"]: continue
                    try:
                        due_str = t["due_date"]
                        if len(due_str) == 10: # YYYY-MM-DD
                            due = datetime.strptime(due_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                        else:
                            due = datetime.fromisoformat(due_str.replace('Z', '+00:00'))
                    except Exception:
                        continue
                        
                    now = datetime.now(timezone.utc)
                    days_left = (due - now).days
                    
                    is_urgent = False
                    if t["type"].lower() == "exam" and 0 <= days_left <= 7:
                        is_urgent = True
                    elif t["type"].lower() in ["assignment", "task"] and 0 <= days_left <= 3:
                        is_urgent = True
                        
                    if is_urgent:
                        should_alert = await asyncio.to_thread(_check_and_mark_mas_alert, t["id"], t["title"], t["type"])
                        if should_alert:
                            clean_title = str(t['title']).replace('{', '{{').replace('}', '}}')
                            alert_text = f"PROACTIVE SYSTEM ALERT: Look at my schedule, I have an upcoming {t['type']} called '{clean_title}' due on {t['due_date']} (in {days_left} days). Stop whatever you are doing and proactively act as my Study Guide! Break down what I need to do, ask me what topics I am weak at, and suggest we schedule focus blocks on the Calendar to prepare. Act like my smart Digimon partner urging me to success!"
                            msg = InboundMessage(
                                channel=channel,
                                sender_id="system",
                                chat_id=chat_id,
                                content=alert_text
                            )
                            logger.info(f"Triggering proactive MAS alert for {clean_title}")
                            await self.bus.publish_inbound(msg)
                            break # Process one alert per loop to avoid spam
            except Exception as e:
                logger.error(f"Proactive MAS loop error: {e}")
                
            # Sleep for an hour before checking again
            await asyncio.sleep(3600)

    async def _proactive_calendar_alerts_loop(self):
        """Background task to poll Google Calendar and trigger real-time panic alerts."""
        while self._running:
            try:
                await asyncio.sleep(60) # check roughly every minute
                
                sessions = self.sessions.list_sessions()
                tg_session = next((s for s in sessions if s["key"].startswith("telegram:")), None)
                if not tg_session:
                    continue
                    
                channel, chat_id = tg_session["key"].split(":", 1)
                
                from nanobot.game.google_api import GoogleIntegration
                google = GoogleIntegration()
                events = await asyncio.to_thread(google.get_upcoming_events)
                if not events:
                    continue
                    
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc)
                
                from nanobot.game.database import SessionLocal
                from nanobot.game import models
                
                def _check_and_mark_alert(eid: str, summary: str) -> bool:
                    db = SessionLocal()
                    try:
                        state_id = f"cal_alert_{eid}"
                        state = db.query(models.TaskSyncState).filter_by(id=state_id).first()
                        if not state:
                            state = models.TaskSyncState(id=state_id, source="calendar", title=summary, status="alerted", task_type="event")
                            db.add(state)
                            db.commit()
                            return True
                        return False
                    finally:
                        db.close()

                for e in events:
                    start_str = e['start'].get('dateTime')
                    if not start_str: 
                        continue # Ignore all-day events
                    
                    if start_str.endswith('Z'):
                        start_str = start_str[:-1] + '+00:00'
                    start_time = datetime.fromisoformat(start_str)
                    start_time_utc = start_time.astimezone(timezone.utc)
                    seconds_until = (start_time_utc - now).total_seconds()
                    
                    # If starting in less than 5 minutes
                    if 0 <= seconds_until <= 300:
                        is_new = await asyncio.to_thread(_check_and_mark_alert, e['id'], e.get('summary', ''))
                        if is_new:
                            # Sanitize summary just in case
                            clean_summary = str(e.get('summary', 'Unknown')).replace('{', '{{').replace('}', '}}')
                            alert_text = f"PROACTIVE SYSTEM ALERT: TAMER! A time block called '{clean_summary}' is starting in {int(seconds_until//60)} minutes! This is your Combat Zone! Tell the Tamer to drop everything and FOCUS!"
                            msg = InboundMessage(
                                channel=channel,
                                sender_id="system",
                                chat_id=chat_id,
                                content=alert_text
                            )
                            logger.info(f"Triggering proactive Calendar alert for {clean_summary}")
                            await self.bus.publish_inbound(msg)
                            break
            except Exception as e:
                logger.error(f"Proactive Calendar loop error: {e}")

    async def _proactive_study_loop(self) -> None:
        """Loop that proactively analyzes study schedule and nudges the Tamer."""
        logger.info("Starting proactive study loop")
        # Initial delay to avoid spamming at startup
        await asyncio.sleep(60)
        
        while self._running:
            try:
                from nanobot.game.study_logic import StudyPlanner
                planner = StudyPlanner()
                suggestions = planner.analyze_schedule()
                
                if suggestions:
                    # Pick the most imminent suggestion
                    s = suggestions[0]
                    
                    message = f"TAMER! 🎓 I've been analyzing your schedule. You have {s['course']} coming up!\n\n"
                    message += f"Smart Study Window: {s['suggested_prep']}\n"
                    if s["materials"]:
                        message += "I found these materials for you:\n"
                        for m in s["materials"]:
                            message += f"🔗 {m['title']}: {m['url']}\n"
                    
                    message += "\nShall I block this time on your calendar for a focused study session?"
                    
                    # Send message to all active sessions
                    active_sessions = self.sessions.list_active_sessions()
                    for session in active_sessions:
                        await self.bus.publish_outbound(OutboundMessage(
                            session_id=session.id,
                            text=message
                        ))
                
                # Run every 4 hours
                await asyncio.sleep(4 * 3600)
            except Exception as e:
                logger.error(f"Error in proactive study loop: {e}")
                await asyncio.sleep(300)

    async def _proactive_daily_scheduler_loop(self):
        """Background task to proactively recommend a daily time-blocked schedule."""
        while self._running:
            try:
                # Run once a day (check every 24 hours essentially, or immediately upon boot with some delay)
                await asyncio.sleep(600) # Boot wait
                
                sessions = self.sessions.list_sessions()
                tg_session = next((s for s in sessions if s["key"].startswith("telegram:")), None)
                if not tg_session:
                    await asyncio.sleep(3600)
                    continue
                    
                channel, chat_id = tg_session["key"].split(":", 1)
                
                alert_text = "DAILY PROACTIVE ROUTINE: It is time to plan the day! Use your ListTasksTool and list_calendar tools. Analyze my unscheduled tasks and upcoming Notion deadlines against my calendar free time. Suggest a highly optimized time-blocking schedule for the next 24-48 hours. Ask me if you should go ahead and use BlockTimeTool to lock these into my calendar!"
                msg = InboundMessage(
                    channel=channel,
                    sender_id="system",
                    chat_id=chat_id,
                    content=alert_text
                )
                logger.info("Triggering Daily Proactive Scheduler Routine")
                await self.bus.publish_inbound(msg)
                
            except Exception as e:
                logger.error(f"Proactive Daily Scheduler loop error: {e}")
                
            # Sleep 24 hours before recommending again
            await asyncio.sleep(86400)

    async def run(self) -> None:
        """Run the agent loop, processing messages from the bus."""
        self._running = True
        await self._connect_mcp()
        logger.info("Agent loop started")
        
        # Start proactive background tasks
        asyncio.create_task(self._proactive_mas_alerts_loop())
        asyncio.create_task(self._proactive_calendar_alerts_loop())
        asyncio.create_task(self._proactive_daily_scheduler_loop())
        asyncio.create_task(self._proactive_study_loop())

        while self._running:
            try:
                msg = await asyncio.wait_for(
                    self.bus.consume_inbound(),
                    timeout=1.0
                )
                try:
                    response = await self._process_message(msg)
                    await self.bus.publish_outbound(response or OutboundMessage(
                        channel=msg.channel, chat_id=msg.chat_id, content="",
                    ))
                except Exception as e:
                    logger.error("Error processing message: {}", e)
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=f"Sorry, I encountered an error: {str(e)}"
                    ))
            except asyncio.TimeoutError:
                continue

    async def close_mcp(self) -> None:
        """Close MCP connections."""
        if self._mcp_stack:
            try:
                await self._mcp_stack.aclose()
            except (RuntimeError, BaseExceptionGroup):
                pass  # MCP SDK cancel scope cleanup is noisy but harmless
            self._mcp_stack = None

    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        logger.info("Agent loop stopping")

    async def _process_message(
        self,
        msg: InboundMessage,
        session_key: str | None = None,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> OutboundMessage | None:
        """
        Process a single inbound message.

        Args:
            msg: The inbound message to process.
            session_key: Override session key (used by process_direct).
            on_progress: Optional callback for intermediate output (defaults to bus publish).

        Returns:
            The response message, or None if no response needed.
        """
        # System messages route back via chat_id ("channel:chat_id")
        if msg.channel == "system":
            return await self._process_system_message(msg)

        preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
        logger.info("Processing message from {}:{}: {}", msg.channel, msg.sender_id, preview)

        key = session_key or msg.session_key
        session = await asyncio.to_thread(self.sessions.get_or_create, key)

        # Handle slash commands
        cmd = msg.content.strip().lower()
        if cmd == "/new":
            # Capture messages before clearing (avoid race condition with background task)
            messages_to_archive = session.messages.copy()
            session.clear()
            await asyncio.to_thread(self.sessions.save, session)
            self.sessions.invalidate(session.key)

            async def _consolidate_and_cleanup():
                temp_session = Session(key=session.key)
                temp_session.messages = messages_to_archive
                await self._consolidate_memory(temp_session, archive_all=True)

            asyncio.create_task(_consolidate_and_cleanup())
            return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id,
                                  content="New session started. Memory consolidation in progress.")
        if cmd == "/help":
            return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id,
                                  content="🐈 nanobot commands:\n/new — Start a new conversation\n/help — Show available commands")

        if len(session.messages) > self.memory_window and session.key not in self._consolidating:
            self._consolidating.add(session.key)

            async def _consolidate_and_unlock():
                try:
                    await self._consolidate_memory(session)
                finally:
                    self._consolidating.discard(session.key)

            asyncio.create_task(_consolidate_and_unlock())

        self._set_tool_context(msg.channel, msg.chat_id, msg.metadata.get("message_id"))
        if message_tool := self.tools.get("message"):
            if isinstance(message_tool, MessageTool):
                message_tool.start_turn()

        initial_messages = await self.context.build_messages(
            history=session.get_history(max_messages=self.memory_window),
            current_message=msg.content,
            media=msg.media if msg.media else None,
            channel=msg.channel,
            chat_id=msg.chat_id,
        )

        # --- FORCED TASK PRE-FETCH ---
        # Gemini refuses to call list_tasks while roleplaying as a baby Digimon.
        # If the user asks about tasks, we pre-execute the tool and inject results
        # directly into the system prompt so the LLM has real data to work with.
        _msg_lower = msg.content.lower()
        _task_triggers = ["task", "to do", "todo", "what should i do", "what do i need", "dark data", "pending"]
        if any(t in _msg_lower for t in _task_triggers):
            try:
                list_tasks_tool = self.tools.get("list_tasks")
                if list_tasks_tool:
                    task_result = await list_tasks_tool.execute()
                    # Inject pre-fetched data into system prompt
                    if initial_messages and initial_messages[0].get("role") == "system":
                        initial_messages[0]["content"] += (
                            f"\n\n--- PRE-FETCHED TASK DATA (use this data in your response!) ---\n"
                            f"{task_result}\n"
                            f"--- END TASK DATA ---\n"
                            f"IMPORTANT: The task data above was retrieved by your Digivice. "
                            f"Present this data to the Tamer in your response. Do NOT say you cannot see tasks."
                        )
                    logger.info("Pre-fetched tasks for system prompt")
            except Exception as e:
                logger.error("Task pre-fetch failed: {}", e)
        # --- END FORCED TASK PRE-FETCH ---

        async def _bus_progress(content: str) -> None:
            meta = dict(msg.metadata or {})
            meta["_progress"] = True
            await self.bus.publish_outbound(OutboundMessage(
                channel=msg.channel, chat_id=msg.chat_id, content=content,
                metadata=meta,
            ))

        final_content, tools_used = await self._run_agent_loop(
            initial_messages, on_progress=on_progress or _bus_progress,
        )

        if final_content is None:
            final_content = "I've completed processing but have no response to give."

        preview = final_content[:120] + "..." if len(final_content) > 120 else final_content
        logger.info("Response to {}:{}: {}", msg.channel, msg.sender_id, preview)

        session.add_message("user", msg.content)
        session.add_message("assistant", final_content,
                            tools_used=tools_used if tools_used else None)
        await asyncio.to_thread(self.sessions.save, session)

        if message_tool := self.tools.get("message"):
            if isinstance(message_tool, MessageTool) and message_tool._sent_in_turn:
                return None

        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=final_content,
            metadata=msg.metadata or {},  # Pass through for channel-specific needs (e.g. Slack thread_ts)
        )

    async def _process_system_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """
        Process a system message (e.g., subagent announce).

        The chat_id field contains "original_channel:original_chat_id" to route
        the response back to the correct destination.
        """
        logger.info("Processing system message from {}", msg.sender_id)

        # Parse origin from chat_id (format: "channel:chat_id")
        if ":" in msg.chat_id:
            parts = msg.chat_id.split(":", 1)
            origin_channel = parts[0]
            origin_chat_id = parts[1]
        else:
            # Fallback
            origin_channel = "cli"
            origin_chat_id = msg.chat_id

        session_key = f"{origin_channel}:{origin_chat_id}"
        session = await asyncio.to_thread(self.sessions.get_or_create, session_key)
        self._set_tool_context(origin_channel, origin_chat_id, msg.metadata.get("message_id"))
        initial_messages = await self.context.build_messages(
            history=session.get_history(max_messages=self.memory_window),
            current_message=msg.content,
            channel=origin_channel,
            chat_id=origin_chat_id,
        )
        final_content, _ = await self._run_agent_loop(initial_messages)

        if final_content is None:
            final_content = "Background task completed."

        session.add_message("user", f"[System: {msg.sender_id}] {msg.content}")
        session.add_message("assistant", final_content)
        await asyncio.to_thread(self.sessions.save, session)

        return OutboundMessage(
            channel=origin_channel,
            chat_id=origin_chat_id,
            content=final_content
        )

    async def _consolidate_memory(self, session, archive_all: bool = False) -> None:
        """Consolidate old messages into MEMORY.md + HISTORY.md.

        Args:
            archive_all: If True, clear all messages and reset session (for /new command).
                       If False, only write to files without modifying session.
        """
        memory = MemoryStore(self.workspace)

        if archive_all:
            old_messages = session.messages
            keep_count = 0
            logger.info("Memory consolidation (archive_all): {} total messages archived", len(session.messages))
        else:
            keep_count = self.memory_window // 2
            if len(session.messages) <= keep_count:
                logger.debug("Session {}: No consolidation needed (messages={}, keep={})", session.key, len(session.messages), keep_count)
                return

            messages_to_process = len(session.messages) - session.last_consolidated
            if messages_to_process <= 0:
                logger.debug("Session {}: No new messages to consolidate (last_consolidated={}, total={})", session.key, session.last_consolidated, len(session.messages))
                return

            old_messages = session.messages[session.last_consolidated:-keep_count]
            if not old_messages:
                return
            logger.info("Memory consolidation started: {} total, {} new to consolidate, {} keep", len(session.messages), len(old_messages), keep_count)

        lines = []
        for m in old_messages:
            if not m.get("content"):
                continue
            tools = f" [tools: {', '.join(m['tools_used'])}]" if m.get("tools_used") else ""
            lines.append(f"[{m.get('timestamp', '?')[:16]}] {m['role'].upper()}{tools}: {m['content']}")
        conversation = "\n".join(lines)
        current_memory = await asyncio.to_thread(memory.read_long_term)

        prompt = f"""You are a memory consolidation agent. Process this conversation and return a JSON object with exactly two keys:

1. "history_entry": A paragraph (2-5 sentences) summarizing the key events/decisions/topics. Start with a timestamp like [YYYY-MM-DD HH:MM]. Include enough detail to be useful when found by grep search later.

2. "memory_update": The updated long-term memory content. Add any new facts: user location, preferences, personal info, habits, project context, technical decisions, tools/services used. If nothing new, return the existing content unchanged.

## Current Long-term Memory
{current_memory or "(empty)"}

## Conversation to Process
{conversation}

**IMPORTANT**: Both values MUST be strings, not objects or arrays.

Example:
{{
  "history_entry": "[2026-02-14 22:50] User asked about...",
  "memory_update": "- Host: HARRYBOOK-T14P\n- Name: Nado"
}}

Respond with ONLY valid JSON, no markdown fences."""

        try:
            response = await self.provider.chat(
                messages=[
                    {"role": "system", "content": "You are a memory consolidation agent. Respond only with valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                model=self.model,
            )
            text = (response.content or "").strip()
            if not text:
                logger.warning("Memory consolidation: LLM returned empty response, skipping")
                return
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            result = json_repair.loads(text)
            if not isinstance(result, dict):
                logger.warning("Memory consolidation: unexpected response type, skipping. Response: {}", text[:200])
                return

            if entry := result.get("history_entry"):
                # Defensive: ensure entry is a string (LLM may return dict)
                if not isinstance(entry, str):
                    entry = json.dumps(entry, ensure_ascii=False)
                await asyncio.to_thread(memory.append_history, entry)
            if update := result.get("memory_update"):
                # Defensive: ensure update is a string
                if not isinstance(update, str):
                    update = json.dumps(update, ensure_ascii=False)
                if update != current_memory:
                    await asyncio.to_thread(memory.write_long_term, update)

            if archive_all:
                session.last_consolidated = 0
            else:
                session.last_consolidated = len(session.messages) - keep_count
            logger.info("Memory consolidation done: {} messages, last_consolidated={}", len(session.messages), session.last_consolidated)
        except Exception as e:
            logger.error("Memory consolidation failed: {}", e)

    async def process_direct(
        self,
        content: str,
        session_key: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
        on_progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        """
        Process a message directly (for CLI or cron usage).

        Args:
            content: The message content.
            session_key: Session identifier (overrides channel:chat_id for session lookup).
            channel: Source channel (for tool context routing).
            chat_id: Source chat ID (for tool context routing).
            on_progress: Optional callback for intermediate output.

        Returns:
            The agent's response.
        """
        await self._connect_mcp()
        msg = InboundMessage(
            channel=channel,
            sender_id="user",
            chat_id=chat_id,
            content=content
        )

        response = await self._process_message(msg, session_key=session_key, on_progress=on_progress)
        return response.content if response else ""
