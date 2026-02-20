# Digimon Partner VPS Deployment Guide

Because the Digimon framework runs an advanced `asyncio` heartbeat loop checking your Tasks and a persistent SQLite database, the system must remain online 24/7. 

## 1. Setup the Daemon
1. Clone this repository onto your VPS.
2. Run `pip install -e .` to install the requirements.
3. Start the daemon using: `nanobot daemon --host 127.0.0.1 --port 8000` (We recommend using `tmux` or `systemd`).

## 2. Reverse Proxy (Caddy)
To securely receive Telegram Webhooks and host the Web App, you must expose the internal FastAPI port to the HTTPS web. Caddy handles SSL certificates automatically.

**Caddyfile**
```caddyfile
your-bot-domain.com {
    reverse_proxy 127.0.0.1:8000
}
```
*Run `systemctl restart caddy` after modifying.*

## 3. Register Telegram Webhook
To tell Telegram where to send user messages:
```bash
curl -F "url=https://your-bot-domain.com/webhook/telegram" https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook
```

## 4. Setup the Mini App
In BotFather (@BotFather):
1. Send `/newapp` or `/mybots > Bot Settings > Menu Button`
2. Enter the URL: `https://your-bot-domain.com/`
3. The Mini App will now load the Digivice directly in Telegram.
