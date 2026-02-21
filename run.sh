#!/bin/bash
# Startup script for Nanobot Gateway

cd "$(dirname "$0")" || exit 1

# Check for virtual environment
if [ ! -d ".venv" ]; then
    echo "Virtual environment not found! Please run 'python3 -m venv .venv && source .venv/bin/activate && pip install -e .' first."
    exit 1
fi

echo "Starting nanobot gateway..."
source .venv/bin/activate

# Execute the nanobot gateway command
nanobot gateway
