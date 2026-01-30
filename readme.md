# Hexmaster — Foxhole Logistics Discord Bot

Hexmaster is a Discord bot for **Foxhole** logistics groups. It tracks **stockpile inventory over time** using **snapshot-based storage** (no overwriting), allowing logistics teams to see changes and trends per town and stockpile across days.

Hexmaster runs on your server via **Docker Compose**, is written in **Python (discord.py 2.x)**, and uses **PostgreSQL** for persistence. Inventory transcription is performed by **FIR (Foxhole Inventory Reporter)** using screenshot → TSV export, driven by a headless worker (Playwright).

---

## What Hexmaster Does (MVP)

- Accepts **one stockpile screenshot per import** via a Discord slash command
- Queues an `import_jobs` record in PostgreSQL
- A worker processes the screenshot through FIR and produces a **TSV** file
- The bot ingests the TSV into PostgreSQL as a **new snapshot** (time-series)
- Supports **multiple Discord guilds** (multi-tenant) via `guild_id`

---

## Architecture

### Services (Docker Compose)

- **hexmaster_bot**
  - discord.py bot
  - SQLAlchemy async + asyncpg
  - Creates database tables on startup
- **postgres**
  - Stores all bot data
- **fir**
  - FIR website (screenshot processing + TSV export)
- **fir_worker**
  - Playwright automation:
    - uploads screenshot to FIR
    - clicks “Download TSV”
    - saves TSV to shared volume
    - marks job DONE or FAILED

---

### Shared Volume Layout

The bot and worker share a filesystem volume:

- Incoming screenshots  
  `/shared/incoming/<guild_id>/<job_id>/<filename>.png`

- Outgoing TSV results  
  `/shared/outgoing/<guild_id>/<job_id>.tsv`

---

## FIR TSV Format (Observed)

FIR exports a TSV with the following headers:

- `Stockpile Title`
- `Stockpile Name`
- `Structure Type`
- `Quantity`
- `Name`
- `Crated?`
- `Per Crate`
- `Total`
- `Description`
- `CodeName`

Example values:
- `Structure Type`: `Seaport`
- `Crated?`: `TRUE`
- `CodeName`: `SoldierSupplies`

Hexmaster uses:
- **Structure Type** from the TSV (no user input)
- **CodeName** as the primary item key (`items.code_name`)

---

## Discord Commands

### `/ping`
Health check and database connectivity test.

### `/import_screenshot town:<Town> stockpile_name:<optional> image:<attachment>`
Imports one stockpile screenshot.

Rules:
- `town` is required and validated against the `towns` table
- `stockpile_name` defaults to **Public** if omitted or blank
- The bot queues a job; ingestion occurs after the FIR worker finishes

### `/stockpile_latest town:<Town> stockpile_name:<optional>`
Shows the latest snapshot metadata  
(summary output will expand once TSV ingestion is complete).

---

## Database Overview

### Global reference tables (shared across all guilds)

- `regions`
- `towns`
- `items` (keyed by `code_name`)

### Guild-scoped tables (isolated by `guild_id`)

- `guilds`
- `guild_item_targets`
- `stockpiles`  
  *(unique: guild + town + structure + stockpile_name)*
- `stockpile_snapshots`
- `snapshot_items`
- `import_jobs`

All timestamps use PostgreSQL **TIMESTAMPTZ**.

---

## Getting Started

### 1) Requirements

- Docker + Docker Compose
- A Discord bot token (`DISCORD_TOKEN`)
- *(Recommended)* A populated `towns` table  
  (imports are rejected if town validation fails)

---

### 2) Configure Environment

Create a `.env` file:

~~~env
DATABASE_URL=postgresql+asyncpg://hexmaster:<PASSWORD>@postgres:5432/hexmaster
DISCORD_TOKEN=<DISCORD_BOT_TOKEN>
POSTGRES_PASSWORD=<POSTGRES_PASSWORD>
~~~

Use placeholders for secrets.  
**Do not commit `.env`.**

---

### 3) Start Services

~~~bash
docker compose up --build
~~~

This starts:
- PostgreSQL
- FIR
- Hexmaster bot
- FIR worker

---

## How the FIR Worker Drives FIR (UI Automation)

The FIR page (as observed from HTML) contains:

- File input  
  `<input accept="image/*" type="file" multiple>`

- TSV download button  
  `<button class="tsv">Download TSV</button>`

The worker uses Playwright to:

1. Open the FIR page (`FIR_BASE_URL`)
2. Set the file input to the screenshot path
3. Wait for FIR processing to complete
4. Click **Download TSV**
5. Capture the download and write it to:  
   `/shared/outgoing/<guild_id>/<job_id>.tsv`

---

## Development Notes

### Towns and Items Data

- The bot validates `town` against the `towns` table
- Items are keyed by `items.code_name` to match FIR `CodeName`
- Optional ordering/numbering (e.g. Stockpiler-style) can be stored via  
  `items.optional_item_number`

---

### Multi-Guild Safety

All guild-owned rows include `guild_id` and **must always be queried with it** to prevent data leakage across servers.

---

### Snapshot Model

Hexmaster **never overwrites inventory**.

Each import creates:
- one `stockpile_snapshot`
- multiple `snapshot_items`

This preserves full historical state.

---

## Troubleshooting

### Import says “Unknown town”
- Populate the `towns` table with valid town names  
  (exact match required).

### Jobs stuck in `QUEUED`
- Confirm `fir_worker` is running
- Confirm PostgreSQL connectivity
- Confirm shared volume paths exist and are writable

### Jobs fail in `PROCESSING`
- Check worker logs
- FIR UI selectors or download handling may need adjustment

---

## Roadmap

- Stabilize Playwright FIR automation
- Implement TSV ingestion → snapshots + items
- Add shortage reporting using `guild_item_targets`
- Add autocomplete for `town`
- Add cleanup for old job files
- Optional: explore API ingestion (FoxAPI) while keeping FIR as fallback

---

## License / Attribution

This project integrates with external tools (FIR) and follows common community conventions (e.g. item naming and ordering).  
Hexmaster’s implementation is intended to remain **clean-room, modular, and server-side only**.
