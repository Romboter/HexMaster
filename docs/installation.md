# Installation & Deployment Guide

This guide covers how to get HexMaster up and running on your own server.

## Prerequisites

- **Docker & Docker Compose**: The recommended way to run HexMaster.
- **Discord Bot Token**: Create one at the [Discord Developer Portal](https://discord.com/developers/applications).
- **Foxhole Stockpiles (FS)**: A running instance of [Foxhole Stockpiles](https://github.com/xurxogr/foxhole-stockpiles) is required for OCR processing.

---

## Installation (Docker)

1.  **Clone the repository**:

    ```bash
    git clone https://github.com/garykuepper/HexMaster.git
    cd HexMaster
    ```

2.  **Configure Environment**:
    Copy `.env.example` to `.env` and fill in your `DISCORD_TOKEN`.

    ```bash
    cp .env.example .env
    nano .env
    ```

3.  **Run with Docker Compose**:
    ```bash
    docker-compose up -d
    ```
    This pulls the latest image and starts the bot and PostgreSQL database.

---

## Development / Building from Source

If you want to build the image locally:

1.  Uncomment `build: .` and comment out `image: ghcr.io/garykuepper/hexmaster:main` in `docker-compose.yml`.
2.  Run `docker-compose up -d --build`.

### Development Scripts

To manually update town data or region offsets:

```bash
python -m scripts.sync_regions
```

---

## Deployment Reference (`docker-compose.yml`)

```yaml
services:
  postgres:
    image: postgres:16
    container_name: hexmaster_db
    environment:
      POSTGRES_DB: hexmaster
      POSTGRES_USER: hexmaster
      POSTGRES_PASSWORD: hexmaster
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U hexmaster"]
      interval: 5s
      timeout: 5s
      retries: 5

  hexmaster_bot:
    image: ghcr.io/garykuepper/hexmaster:main
    container_name: hexmaster_bot
    restart: always
    depends_on:
      postgres:
        condition: service_healthy
    env_file:
      - .env
    environment:
      - DATABASE_URL=postgresql+asyncpg://hexmaster:hexmaster@127.0.0.1:5432/hexmaster
      - OCR_URL=http://localhost:8000
      - WARAPI_BASE_URL=https://war-service-live.foxholeservices.com/api
      - DISCORD_GUILD_ID=175795857138909185
    volumes:
      - shared_data:/app/shared
    network_mode: host

volumes:
  pgdata:
  shared_data:
```
