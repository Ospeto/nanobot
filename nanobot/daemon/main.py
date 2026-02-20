import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
from io import BytesIO
from PIL import Image
import httpx

from nanobot.game.database import init_db, SessionLocal
from nanobot.game.sync import SyncManager
from nanobot.daemon.twa import validate_telegram_init_data
from nanobot.game import state

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
    
    if os.getenv("ENV") != "dev" and not validate_telegram_init_data(init_data, bot_token):
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
    
    if os.getenv("ENV") != "dev" and not validate_telegram_init_data(init_data, bot_token):
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
    
    if os.getenv("ENV") != "dev" and not validate_telegram_init_data(init_data, bot_token):
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
async def twa_get_evolution_tree(request: Request):
    body = await request.json()
    init_data = body.get("initData")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "dummy")
    
    if os.getenv("ENV") != "dev" and not validate_telegram_init_data(init_data, bot_token):
        raise HTTPException(status_code=401, detail="Invalid Telegram signature")

    db = SessionLocal()
    try:
        from nanobot.game.encyclopedia import Digipedia
        active = state.get_active_digimon(db)
        if not active or active.name == "Digitama":
            return {"current": "Digitama", "prev": None, "next": []}
            
        info = await Digipedia.get_digimon_info(active.name)
        if not info:
            return {"current": active.name, "prev": None, "next": []}
            
        prior = info.get("priorEvolutions", [])
        next_evos = info.get("nextEvolutions", [])
        
        prev_data = None
        if prior:
            prev_data = {
                "name": prior[0].get("digimon"),
                "image": prior[0].get("image")
            }
        
        # take up to 2 next evolutions
        next_list = []
        for n in next_evos:
            valid_image = n.get("image")
            if not valid_image:
                continue
            next_list.append({
                "name": n.get("digimon"),
                "condition": n.get("condition"),
                "image": valid_image
            })
            if len(next_list) >= 2:
                break
            
        return {
            "current": active.name,
            "current_image": info.get("images", [{}])[0].get("href") if info.get("images") else None,
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
    
    if os.getenv("ENV") != "dev" and not validate_telegram_init_data(init_data, bot_token):
        raise HTTPException(status_code=401, detail="Invalid Telegram signature")

    db = SessionLocal()
    try:
        from nanobot.game.weather import get_weather_condition
        from nanobot.game.evolution import hatch_digitama
        import datetime
        from datetime import timezone
        
        active = state.get_active_digimon(db)
        if not active or active.stage != "Digitama":
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
    except Exception as e:
        db.rollback()
        print(f"Error hatching egg: {e}")
        raise HTTPException(status_code=500, detail="Internal error during hatching.")
    finally:
        db.close()

@app.get("/twa/api/sprite/{name}")
async def proxy_digimon_sprite(name: str):
    """
    Proxies the image from digi-api and strips out the white background
    pixel-by-pixel using Pillow.
    """
    url = f"https://digi-api.com/images/digimon/w/{name}.png"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10.0)
            resp.raise_for_status()

            img = Image.open(BytesIO(resp.content)).convert("RGBA")
            data = img.getdata()
            new_data = []
            
            # Strip white/light-grey backgrounds natively
            for item in data:
                if item[0] > 240 and item[1] > 240 and item[2] > 240:
                    new_data.append((255, 255, 255, 0)) # Alpha 0 (Transparent)
                else:
                    new_data.append(item)
                    
            img.putdata(new_data)
            
            output = BytesIO()
            img.save(output, format="PNG")
            output.seek(0)
            
            return StreamingResponse(output, media_type="image/png")
            
        except Exception as e:
            print(f"Error fetching sprite {name}: {e}")
            # Return empty 1x1 transparent PNG on error
            empty_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0bIDAT\x08\xd7c\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
            return StreamingResponse(BytesIO(empty_png), media_type="image/png")

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "digimon_daemon"}
