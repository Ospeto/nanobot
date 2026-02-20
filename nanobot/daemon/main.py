import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from nanobot.game.database import init_db
from nanobot.game.sync import SyncManager
from nanobot.daemon.twa import validate_telegram_init_data
from fastapi import FastAPI
from nanobot.game.database import init_db

async def background_sync_loop():
    while True:
        try:
            # TODO: Implement sync logic here
            # sync_vital_decay()
            # sync_google_tasks()
            # sync_notion_tasks()
            await asyncio.sleep(60) # Run every 60 seconds
        except asyncio.CancelledError:
            print("Background sync loop cancelled.")
            break
        except Exception as e:
            print(f"Error in background loop: {e}")
            await asyncio.sleep(60)

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
        
    return {
        "active_digimon": {
            "name": "Agumon",
            "hp": 80,
            "energy": 90,
            "hunger": 50,
            "bond": 10,
            "level": 1
        }
    }

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "digimon_daemon"}
