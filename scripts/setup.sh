#!/bin/bash

# HexMaster Setup Script
# Automates environment configuration, container startup, and firewall rules.

set -e

echo "🚀 Starting HexMaster Setup..."

# 1. Ensure .env exists
if [ ! -f .env ]; then
    echo "📄 .env not found. Creating from .env.example..."
    cp .env.example .env
    echo "⚠️ Please edit .env and provide your DISCORD_TOKEN and POSTGRES_PASSWORD."
    # We'll continue, but the bot might fail until token is provided
else
    echo "✅ .env file already exists."
fi

# 2. Start Docker containers
echo "📦 Starting Docker containers..."
docker compose up -d

# 3. Inform user about networking
echo "✅ Using Host Networking. Bot can reach host services via 'localhost'."

echo "✨ Setup complete! Use 'docker compose logs -f hexmaster_bot' to check bot status."
