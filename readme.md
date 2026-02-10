# HexMaster — Foxhole Logistics Discord Bot

HexMaster is a powerful Discord bot designed for **Foxhole** logistics groups. It enables seamless stockpile management, cross-map item discovery, and intelligent supply chain comparison using OCR and real-time game data.

The bot follows a **snapshot-based storage** model, preserving full historical data of every stockpile update without ever overwriting.

---

## What HexMaster Does (MVP)

### 1. Intelligence Reporting

- **Filing Reports**: Users file intelligence reports by uploading screenshots of stockpiles via the `/report` slash command.
- **Deep Processing**: The bot uses an OCR service to transcribe item codes, names, total quantities, and crate statuses.
- **Historical snapshots**: Every import creates a new time-stamped record for trend analysis.

### 2. Requisition Orders

- **Supply Chain Decisioning**: Compare a "Shipping Hub" (e.g., Seaport/Warehouse) against a "Receiving Town/Base".
- **Hub Detection**: Automatically detects Seaports and Storage Warehouses to apply a **4x requirement multiplier**.
- **Crate-First Units**: All quantities are standardized to "Crates" for easy logistics math.
- **Priority Logic**: Sorts items by mission-critical importance and highlights shortages.

### 3. Strategic Reconnaissance

- **Global Search**: Find which stockpiles currently hold a specific item across the entire World Conquest map.
- **Accurate Hex Math**: Uses a custom **Cartesian-Staggered** coordinate system to calculate distances in physical hex units.
- **Proximity Sorting**: Results are sorted by distance from your reference town.
- **Sync with WarAPI**: Automatically fetches 918+ town locations and marker types (Major/Minor) from the official Foxhole servers.

---

## Quick Reference 🚀

### User Commands

| Command          | Description                                                           |
| ---------------- | --------------------------------------------------------------------- |
| `/report`        | **File an Intelligence Report** by uploading a stockpile screenshot.  |
| `/inventory`     | **View the Inventory** for a specific town or base.                   |
| `/locate`        | **Perform Reconnaissance** to find an item's location across the map. |
| `/requisition`   | **Calculate a Requisition Order** to identify supply gaps.            |
| `/priority list` | **View the Priority List** for your current server.                   |
| `/help`          | Display the command list and lore.                                    |

### Admin Commands (Administrator Permission Required)

| Command             | Description                                         |
| ------------------- | --------------------------------------------------- |
| `/setup config`     | **Configure Server** settings (Faction, Shard).     |
| `/setup priorities` | **Load Priority Templates** or clear existing ones. |
| `/priority add`     | **Add/Update Item** in the priority list.           |
| `/priority remove`  | **Remove Item** from the priority list.             |

---

## Server Setup (Admins Only)

Once the bot is invited to your server, you **must** configure it before it can fetch accurate game data or track stockpiles:

1. **Configure Faction & Shard**: Run `/setup config faction:[Colonial/Warden] shard:[Alpha/Bravo/Charlie]`. This tells the bot which WarAPI endpoint to use and which faction items to prioritize.
2. **Initialize Priorities**: Run `/setup priorities template:standard` to load a default list of 60+ critical logistics items. You can further customize these with `/priority add` and `/priority remove`.

---

## Architecture

- **Discord Bot**: Built with `discord.py` and `SQLAlchemy`.
- **Database**: PostgreSQL with `asyncpg` for high-performance async queries.
- **Sync Logic**: Standalone Python scripts for seeding regions and syncing with WarAPI.
- **Dockerized**: Fully containerized for easy deployment on Linux/Windows.

---

## Future Roadmap & UI Updates

While the core logic is now stable, the following UI and feature enhancements are planned:

- **Dynamic Inventory Cleanup**: Automatically remove or "grey out" inventories for Seaports or Storage Warehouses that the WarAPI reports as **Destroyed** or **Captured** by the enemy.
- **Faction Tracking**: Only show inventories that belong to the bot-owner's faction (Colonials/Wardens) in real-time.
- **Logistics Threat Mapping**: Overlay current "Front Line" map data to warn logistics drivers if a `/locate` result requires driving through contested or enemy-held territory.
- **Supply Drop Alerts**: Automated pings when a critical frontline base (based on WarAPI status) is low on Soldier Supplies or AT weapons.
- **Trend Charts**: Visual graphs of stockpile changes over the last 24-48 hours.

---

## Getting Started

### 1) Prerequisites

- Docker & Docker Compose
- Discord Bot Token
- **Headless FIR Service**: A running instance of the [FIR (Headless Fork)](https://github.com/garykuepper/fir).

### 2) Environment Setup

Create a `.env` file from `.env.example`:

```env
DISCORD_TOKEN=your_token_here
DATABASE_URL=postgresql+asyncpg://hexmaster:hexmaster@postgres:5432/hexmaster
OCR_URL=http://your_ocr_service_ip:5000
```

### 3) Launch

Start the bot and database:

```bash
docker compose up --build -d
```

### 4) Deployment Reference

For transparency, here is the `docker-compose.yml` used to orchestrate the containers:

```yaml
services:
  postgres:
    image: postgres:16
    container_name: hexmaster_db
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 5s
      timeout: 5s
      retries: 5

  hexmaster_bot:
    build: .
    container_name: hexmaster_bot
    restart: always
    depends_on:
      postgres:
        condition: service_healthy
    env_file:
      - .env
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - OCR_URL=${OCR_URL}
    volumes:
      - shared_data:/app/shared
    network_mode: host

volumes:
  pgdata:
  shared_data:
```

---

## Development & Seeding

To update town data or region offsets manually:

```bash
python -m scripts.sync_regions
```

---

## Technical Reference

- **Bot Implementation**: `src/hexmaster/bot/main.py`
- **Database Schema**: `src/hexmaster/db/schema.sql` (managed automatically via `init_db`)
- **Reference Data**: Located in `data/` (Towns, Regions, Catalog)

---

## Credits & Attribution

HexMaster relies on several critical community-maintained tools and APIs:

- **FIR (Foxhole Inventory Reporter)**: All OCR and screenshot-to-data logic is powered by the [Headless FIR Fork](https://github.com/garykuepper/fir) (originally by GICodeWarrior).
- **Foxhole WarAPI**: Live town data, map status, and hex regions are provided by the official [WarAPI](https://github.com/clapfoot/warapi) maintained by Clapfoot/Siege Camp.
- **Discord.py**: High-level Discord API wrapper.
- **SQLAlchemy & asyncpg**: Database abstraction and performance.

## License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for the full text.

HexMaster's implementation is intended for private logistics group use and follows all community safety standards for Foxhole third-party software.
