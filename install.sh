#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}=======================================${NC}"
echo -e "${GREEN}   Nanobot Digimon Partner Installer   ${NC}"
echo -e "${BLUE}=======================================${NC}\n"

# 1. Gather User Configuration

echo -e "${YELLOW}Step 1: Configuration${NC}"

# Telegram Bot Token
read -p "Enter your Telegram Bot Token: " TELEGRAM_TOKEN
while [[ -z "$TELEGRAM_TOKEN" ]]; do
    echo "Telegram Token is required to start the bot."
    read -p "Enter your Telegram Bot Token: " TELEGRAM_TOKEN
done

# Telegram User ID
read -p "Enter your Telegram User ID (numbers only, no @): " TELEGRAM_USER_ID
while [[ -z "$TELEGRAM_USER_ID" ]]; do
    echo "Telegram User ID is required to authorize commands."
    read -p "Enter your Telegram User ID (numbers only, no @): " TELEGRAM_USER_ID
done

# Domain Name
echo -e "\n${YELLOW}To run the Web App, Caddy needs a domain name for SSL generation.${NC}"
echo "If you are running this locally without a domain, press Enter to default to 'localhost'."
read -p "Enter your Domain Name (e.g., bot.example.com) [localhost]: " DOMAIN_NAME
DOMAIN_NAME=${DOMAIN_NAME:-localhost}

# LLM Selection
echo -e "\n${YELLOW}Which AI Provider do you want to use?${NC}"
echo "1) OpenRouter (Recommended)"
echo "2) OpenAI"
echo "3) Anthropic"
echo "4) Gemini"
echo "5) None (Not recommended, Evolutions will use fallback math)"
read -p "Select [1-5]: " LLM_CHOICE

PROVIDER_KEY="openrouter"
MODEL_NAME="openrouter/anthropic/claude-3.5-sonnet:beta"

case $LLM_CHOICE in
    1)
        PROVIDER_KEY="openrouter"
        MODEL_NAME="openrouter/anthropic/claude-3.5-sonnet:beta"
        read -p "Enter your OpenRouter API Key: " LLM_API_KEY
        ;;
    2)
        PROVIDER_KEY="openai"
        MODEL_NAME="gpt-4o"
        read -p "Enter your OpenAI API Key: " LLM_API_KEY
        ;;
    3)
        PROVIDER_KEY="anthropic"
        MODEL_NAME="claude-3-5-sonnet-20241022"
        read -p "Enter your Anthropic API Key: " LLM_API_KEY
        ;;
    4)
        PROVIDER_KEY="gemini"
        # Using LiteLLM's prefix standard
        MODEL_NAME="gemini/gemini-2.5-flash"
        read -p "Enter your Gemini API Key: " LLM_API_KEY
        ;;
    5)
        LLM_API_KEY=""
        ;;
    *)
        echo "Invalid selection, defaulting to OpenRouter with no key."
        LLM_API_KEY=""
        ;;
esac

# Brave Search (Optional Web Capability)
echo -e "\n${YELLOW}Would you like to enable Web Search capabilities? (Requires Brave Search API)${NC}"
read -p "Enter your Brave Search API Key (Leave blank to skip): " BRAVE_API_KEY

# 2. Write Configurations

echo -e "\n${BLUE}=======================================${NC}"
echo -e "${YELLOW}Step 2: Writing Configuration Files${NC}"

# Write .env file
echo "ENV=prod" > .env
echo "TELEGRAM_BOT_TOKEN=$TELEGRAM_TOKEN" >> .env
echo "Wrote .env"

# Write Caddyfile
cat > Caddyfile << EOF
$DOMAIN_NAME {
    reverse_proxy nanobot-daemon:8000
}
EOF
echo "Wrote Caddyfile"

# Write ~/.nanobot/config.json
mkdir -p ~/.nanobot
if [[ -n "$LLM_API_KEY" ]]; then
    cat > ~/.nanobot/config.json << EOF
{
  "agents": {
    "defaults": {
      "model": "$MODEL_NAME"
    }
  },
  "providers": {
    "$PROVIDER_KEY": {
      "apiKey": "$LLM_API_KEY"
    }
  },
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "$TELEGRAM_TOKEN",
      "allowFrom": ["$TELEGRAM_USER_ID"]
    }
  }$(if [[ -n "$BRAVE_API_KEY" ]]; then echo ",
  \"tools\": {
    \"web\": {
      \"search\": {
        \"apiKey\": \"$BRAVE_API_KEY\"
      }
    }
  }"; fi)
}
EOF
    echo "Wrote ~/.nanobot/config.json"
else
    cat > ~/.nanobot/config.json << EOF
{
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "$TELEGRAM_TOKEN",
      "allowFrom": ["$TELEGRAM_USER_ID"]
    }
  }$(if [[ -n "$BRAVE_API_KEY" ]]; then echo ",
  \"tools\": {
    \"web\": {
      \"search\": {
        \"apiKey\": \"$BRAVE_API_KEY\"
      }
    }
  }"; fi)
}
EOF
    echo "Wrote ~/.nanobot/config.json (without AI keys)"
fi


# 3. Docker Initialization
echo -e "\n${BLUE}=======================================${NC}"
echo -e "${YELLOW}Step 3: Building and Starting Docker${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "${GREEN}Docker is not installed. Please install Docker and Docker Compose, then re-run this script.${NC}"
    exit 1
fi

echo "Building nanobot-daemon Docker image..."
docker compose build nanobot-daemon

echo "Starting Docker Compose stack..."
docker compose up -d

# 4. Final Output
echo -e "\n${BLUE}=======================================${NC}"
echo -e "${GREEN}Installation Complete!${NC}"
echo -e "Your API server is running in the background."

if [[ "$DOMAIN_NAME" == "localhost" ]]; then
    echo -e "\n${YELLOW}Since you are using localhost, you will need a tunnel like Ngrok or Cloudflare to receive Telegram Webhooks.${NC}"
    echo "Example: 'ngrok http 80'"
else
    echo -e "\n${GREEN}To register your domain with Telegram, run this command:${NC}"
    echo "curl -F \"url=https://$DOMAIN_NAME/webhook/telegram\" https://api.telegram.org/bot$TELEGRAM_TOKEN/setWebhook"
fi

echo -e "\nTo view live logs, use: ${YELLOW}docker compose logs -f nanobot-daemon${NC}"
echo -e "${BLUE}=======================================${NC}\n"
