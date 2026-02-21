import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
from io import BytesIO
from PIL import Image
import httpx

from nanobot.game.database import init_db, SessionLocal
from nanobot.game.sync import SyncManager
from nanobot.daemon.twa import validate_telegram_init_data
from nanobot.game import state
from nanobot.game.assets import AssetManager

async def background_sync_loop():
    manager = SyncManager()
    await manager.run_sync_loop()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize DB
    init_db()
    
    # Startup: Start Background Sync Loop
    task = asyncio.create_task(background_sync_loop())
    yield
    # Shutdown: Clean up task
    task.cancel()

app = FastAPI(title="Nanobot Digimon Daemon", lifespan=lifespan)

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_digivice():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r") as f:
            return f.read()
    return "<h1>Digivice Not Initialized</h1>"

@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    data = await request.json()
    # TODO: Route messages to nanobot AgentLoop
    return {"status": "ok"}

@app.post("/twa/api/vitals")
async def twa_get_vitals(request: Request):
    body = await request.json()
    init_data = body.get("initData")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "dummy")
    
    # Allow bypass if local testing explicitly sends 'dummy'
    is_dev = os.getenv("ENV", "dev") == "dev" or init_data == "dummy"
    if not is_dev and not validate_telegram_init_data(init_data, bot_token):
        raise HTTPException(status_code=401, detail="Invalid Telegram signature")

    db = SessionLocal()
    try:
        active = state.get_active_digimon(db)
        inv = state.get_or_create_inventory(db)
        
        if active:
            sprite_name = active.species.replace(" ", "_") if active.species else active.name
            return {
                "active_digimon": {
                    "name": active.name,
                    "hp": int((active.current_hp / max(active.max_hp, 1)) * 100),
                    "energy": active.energy,
                    "hunger": active.hunger,
                    "bond": active.bond,
                    "level": active.level,
                    "sprite": f"/twa/api/sprite/{sprite_name}",
                    "bits": inv.bits
                }
            }
        
        # Fallback if no active digimon
        return {
            "active_digimon": {
                "name": "Digitama",
                "hp": 100,
                "energy": 100,
                "hunger": 100,
                "bond": 0,
                "level": 0,
                "sprite": "/twa/api/sprite/Digitama",
                "bits": 0
            }
        }
    finally:
        db.close()

@app.post("/twa/api/tasks")
async def twa_get_tasks(request: Request):
    body = await request.json()
    init_data = body.get("initData")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "dummy")
    
    is_dev = os.getenv("ENV", "dev") == "dev" or init_data == "dummy"
    if not is_dev and not validate_telegram_init_data(init_data, bot_token):
        raise HTTPException(status_code=401, detail="Invalid Telegram signature")

    db = SessionLocal()
    try:
        from nanobot.game.models import TaskSyncState
        tasks = db.query(TaskSyncState).filter(TaskSyncState.status == "pending").all()
        return {
            "tasks": [
                {
                    "id": t.id,
                    "source": t.source,
                    "title": t.title,
                    "attribute": t.attribute,
                }
                for t in tasks
            ]
        }
    finally:
        db.close()

@app.post("/twa/api/tasks/{task_id}/complete")
async def twa_complete_task(task_id: str, request: Request):
    body = await request.json()
    init_data = body.get("initData")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "dummy")
    
    is_dev = os.getenv("ENV", "dev") == "dev" or init_data == "dummy"
    if not is_dev and not validate_telegram_init_data(init_data, bot_token):
        raise HTTPException(status_code=401, detail="Invalid Telegram signature")

    db = SessionLocal()
    try:
        from nanobot.game.models import TaskSyncState
        from nanobot.game.combat import Enemy, resolve_combat
        
        task = db.query(TaskSyncState).filter(TaskSyncState.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        if task.status == "completed":
            return {"status": "already_completed"}
            
        success = False
        if task.source == "notion":
            from nanobot.game.notion_api import NotionIntegration
            success = NotionIntegration().complete_task(task.id)
        elif task.source == "google_tasks":
            from nanobot.game.google_api import GoogleIntegration
            success = GoogleIntegration().complete_task(task.id)
            
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to complete task in upstream {task.source}")
            
        task.status = "completed"
        enemy = Enemy(task_source=task.source, task_id=task.id, title=task.title, status="completed")
        combat_result = resolve_combat(db, enemy)
        
        db.commit()
        
        return {
            "status": "success",
            "combat_result": combat_result
        }
    finally:
        db.close()

@app.post("/twa/api/evolution_tree")
async def twa_get_evolution_tree(request: Request, background_tasks: BackgroundTasks):
    body = await request.json()
    init_data = body.get("initData")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "dummy")
    
    is_dev = os.getenv("ENV", "dev") == "dev" or init_data == "dummy"
    if not is_dev and not validate_telegram_init_data(init_data, bot_token):
        raise HTTPException(status_code=401, detail="Invalid Telegram signature")

    db = SessionLocal()
    try:
        from nanobot.game.encyclopedia import Digipedia
        from nanobot.game.models import EvolutionRule
        from nanobot.game.evolution import generate_evolution_conditions
        
        active = state.get_active_digimon(db)
        if not active or active.name == "Digitama":
            return {"current": "Digitama", "prev": None, "next": []}
            
        info = await Digipedia.get_digimon_info(active.name)
        if not info:
            return {"current": active.name, "prev": None, "next": []}
            
        prior = info.get("evolvesFrom", [])
        next_evos = info.get("evolvesTo", [])
        
        prev_data = None
        if prior:
            prev_name = prior[0].get("name")
            prev_data = {
                "name": prev_name,
                "image": f"/twa/api/sprite/{prev_name}" if prev_name else None
            }
        
        # take up to 2 next evolutions
        next_list = []
        for n in next_evos:
            target_name = n.get("name")
            if not target_name:
                continue
                
            # Filter non-canon for a cleaner tree
            if not n.get("canon"):
                continue
            
            valid_image = f"/twa/api/sprite/{target_name}"
            
            # Check for AI-generated rule in DB
            rule = db.query(EvolutionRule).filter_by(base_digimon=active.name, target_digimon=target_name).first()
            if rule:
                cond = rule.condition_string
            else:
                # Trigger LLM Generation Background Task
                background_tasks.add_task(generate_evolution_conditions, active.name, target_name)
                cond = "Analyzing Data..."

            next_list.append({
                "name": target_name,
                "condition": cond,
                "image": valid_image
            })
            if len(next_list) >= 2:
                break
            
        return {
            "current": active.name,
            "current_image": f"/twa/api/sprite/{active.name}",
            "prev": prev_data,
            "next": next_list
        }
    except Exception as e:
        print(f"Error fetching evo tree: {e}")
        return {"current": "Unknown", "prev": None, "next": []}
    finally:
        db.close()

@app.post("/twa/api/hatch")
async def twa_hatch_egg(request: Request):
    """
    Evaluates weather and time passed from frontend to hatch the Digitama.
    """
    body = await request.json()
    init_data = body.get("initData")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "dummy")
    
    is_dev = os.getenv("ENV", "dev") == "dev" or init_data == "dummy"
    if not is_dev and not validate_telegram_init_data(init_data, bot_token):
        raise HTTPException(status_code=401, detail="Invalid Telegram signature")

    db = SessionLocal()
    try:
        from nanobot.game.weather import get_weather_condition
        from nanobot.game.evolution import hatch_digitama
        import datetime
        from datetime import timezone
        from nanobot.game.models import DigimonState
        
        active = state.get_active_digimon(db)
        if not active:
            # Fallback initialization organically skipping CLI tool
            active = DigimonState(name="Digitama", species="Digitama", stage="Digitama", 
                                 attribute="None", element="None", level=0, is_active=True)
            db.add(active)
            db.flush()
            
        if active.stage != "Digitama":
            raise HTTPException(status_code=400, detail="No active Digitama to hatch.")
            
        if active.hatch_time:
            hatch_dt = datetime.datetime.fromisoformat(active.hatch_time)
            if datetime.datetime.utcnow() < hatch_dt:
                remaining = int((hatch_dt - datetime.datetime.utcnow()).total_seconds())
                raise HTTPException(status_code=400, detail=f"Egg is not ready. Try again in {remaining} seconds.")
                
        lat = body.get("latitude", 0.0)
        lon = body.get("longitude", 0.0)
        offset_minutes = body.get("utc_offset", 0) # E.g., -420 for PDT
        
        # Calculate local hour
        utc_now = datetime.datetime.now(timezone.utc)
        local_time = utc_now + datetime.timedelta(minutes=offset_minutes)
        local_hour = local_time.hour
        
        weather = await get_weather_condition(lat, lon)
        result = hatch_digitama(weather=weather, hour=local_hour)
        
        active.species = result["species"]
        active.name = result["name"]
        active.stage = result["stage"]
        active.attribute = result["attribute"]
        active.element = result["element"]
        active.level = result["level"]
        active.max_hp = 100
        active.current_hp = 100
        active.hunger = 100
        active.energy = 100
        active.hatch_time = None
        
        db.commit()
        
        return {
            "status": "success",
            "digimon": {
                "name": active.name,
                "species": active.species,
                "weather_cond": weather,
                "time_hour": local_hour
            }
        }
    except HTTPException as he:
        db.rollback()
        raise he
    except Exception as e:
        db.rollback()
        print(f"Error hatching egg: {e}")
        raise HTTPException(status_code=500, detail="Internal error during hatching.")
    finally:
        db.close()

@app.get("/twa/api/sprite/{name}")
async def proxy_digimon_sprite(name: str):
    """
    Returns the Digimon sprite from the local cache via AssetManager,
    falling back to a transparent pixel if not found.
    """
    sprite_path = await AssetManager.get_sprite_path(name)
    if sprite_path and os.path.exists(sprite_path):
        from fastapi.responses import FileResponse
        return FileResponse(sprite_path, media_type="image/png")
        
    print(f"Sprite not found for {name}")
    empty_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0bIDAT\x08\xd7c\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
    return StreamingResponse(BytesIO(empty_png), media_type="image/png")

@app.post("/twa/api/action")
async def twa_digimon_action(request: Request):
    """
    Handles simple actions like Feed, Play, Clean from the Minigame.
    """
    body = await request.json()
    init_data = body.get("initData")
    action = body.get("action")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "dummy")
    
    is_dev = os.getenv("ENV", "dev") == "dev" or init_data == "dummy"
    if not is_dev and not validate_telegram_init_data(init_data, bot_token):
        raise HTTPException(status_code=401, detail="Invalid Telegram signature")

    db = SessionLocal()
    try:
        active = state.get_active_digimon(db)
        if not active:
            raise HTTPException(status_code=400, detail="No active Digimon")
            
        if action == "feed":
            res = state.feed_digimon(db, active.id, "Meat")
            db.commit()
            return {"status": "success", "result": res}
        elif action == "play":
            # Very basic play implementation until we have complex minigames
            active.energy = max(0, active.energy - 10)
            active.hunger = max(0, active.hunger - 10)
            active.exp += 15
            active.bond = min(100, active.bond + 5)
            db.commit()
            return {"status": "success", "message": "Played with partner!"}
        elif action == "clean":
            active.bond = min(100, active.bond + 2)
            db.commit()
            return {"status": "success", "message": "Cleaned up area."}
        else:
            raise HTTPException(status_code=400, detail="Unknown action")
    finally:
        db.close()


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "digimon_daemon"}
