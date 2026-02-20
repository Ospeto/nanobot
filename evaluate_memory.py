import os
import asyncio
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic

async def main():
    client = AsyncAnthropic() # uses ANTHROPIC_API_KEY from environment
    
    system_prompt = """You are an AI Memory Architecture expert participating in a debate.
    
    ## The System Being Evaluated
    The system is a virtual pet (Digimon) integrated into an AI assistant agent. It uses two parallel memory systems:
    
    1. Subconscious Memory (MEMORY.md): An unstructured markdown file summarizing past conversations. It is automatically appended to by a background LLM process every 50 messages.
    2. Conscious Memory (SecondBrain SQLite): A structured Graph database where the agent explicitly calls `add_memory_node(type, name, properties)` and `link_memory_nodes(source, target, relation)`. 
    
    ## The Personas
    You will simulate a debate between three experts based on these skill archetypes:
    - **Persona A (AI Engineer):** Focuses on production RAG, latency, token costs, and structured outputs.
    - **Persona B (Cognitive Architect - `agent-memory-systems`):** Focuses on memory retrieval, chunking, memory types (episodic vs semantic), and the psychological/cognitive aspects of memory.
    - **Persona C (MCP Tool Builder - `agent-memory-mcp`):** Focuses on the system integration, persistent tooling, and dashboard observability.
    
    ## Instructions
    Evaluate how well these two systems (Subconscious markdown vs Conscious SQLite Graph) work together. 
    1. Discuss the strengths of this dual approach.
    2. Discuss the weaknesses and potential failure modes (e.g. data desync, missing retrieval).
    3. Debate improvement suggestions.
    
    Format the output as a transcript of their conversation. Keep it highly technical and insightful.
    """
    
    try:
        response = await client.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=4000,
            system=system_prompt,
            messages=[
                {"role": "user", "content": "Please begin the evaluation debate."}
            ]
        )
        print("\n--- DEBATE OUTPUT ---\n")
        print(response.content[0].text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
