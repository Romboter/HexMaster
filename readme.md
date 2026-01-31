# Hexmaster — Foxhole Logistics Discord Bot

Hexmaster is a Discord bot for **Foxhole** logistics groups. It tracks **stockpile inventory over time** using *
*snapshot-based storage** (no overwriting), allowing logistics teams to see changes and trends per town and stockpile
across days.

Hexmaster runs on your server via **Docker Compose**, is written in **Python (discord.py 2.x)**, and uses **PostgreSQL**
for persistence. Inventory transcription is performed by **FIR (Foxhole Inventory Reporter)** using screenshot → TSV
export, driven by a headless worker (Playwright).

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

## Roadmap Phases

### Phase 0 — Repo + Docker Skeleton

**Goal:** bootable stack that runs locally and on your Ubuntu server.

- [ ] Create repo layout (`bot/`, `fir_worker/`, `shared/`, `docker-compose.yml`, `.env.example`)
- [ ] Docker Compose services: `postgres`, `hexmaster_bot`
- [ ] Bot boots, connects to DB, logs in to Discord
- [ ] `/ping` command works
- [ ] Basic logging + env config loading

**Exit criteria:** `docker compose up --build` starts and `/ping` replies.

---

### Phase 1 — Database Foundation

**Goal:** schema is stable and supports multi-guild + time-series.

- [ ] SQLAlchemy async setup (`asyncpg`)
- [ ] ORM models + migrations (or `create_all` for early stage)
- [ ] Tables:
    - [ ] `guilds` (auto-register on join)
    - [ ] `regions`, `towns` (global reference)
    - [ ] `items` (global)
    - [ ] `guild_item_targets` (guild-scoped)
- [ ] Constraints + indexes (at least the important uniques)

**Exit criteria:** DB tables created; bot auto-inserts guild on invite; can query towns/items.

---

### Phase 2 — Import Job Queue + Screenshot Command

**Goal:** user can submit a screenshot via a slash command and it becomes a queued job.

- [ ] Add `import_jobs` table + job states (`QUEUED`, `PROCESSING`, `DONE`, `FAILED`)
- [ ] Slash command:
    - [ ] `/import_screenshot town:<Town> stockpile_name:<optional> image:<attachment>`
- [ ] Behavior:
    - [ ] Validate town exists in `towns`
    - [ ] Default `stockpile_name` to `"Public"`
    - [ ] Save image to `/shared/incoming/<guild_id>/<job_id>/...`
    - [ ] Insert `import_jobs` row with metadata (guild_id, town_name, stockpile_name, file path)

**Exit criteria:** command saves the file + creates a queued job row reliably.

---

### Phase 3 — FIR Service in Docker

**Goal:** FIR is running inside the same compose network.

- [ ] Add `fir` service to docker-compose (port exposed optionally)
- [ ] Confirm `fir_worker` container can reach FIR via `http://fir:8000`
- [ ] Add shared volume wiring (`/shared`)

**Exit criteria:** FIR is reachable from within Docker network.

---

### Phase 4 — FIR Worker Automation (Playwright)

**Goal:** worker picks up queued jobs, runs FIR headlessly, outputs TSV.

- [ ] Add `fir_worker` service (Playwright Python image)
- [ ] Worker loop:
    - [ ] poll DB for `QUEUED` jobs
    - [ ] mark job `PROCESSING`
    - [ ] open FIR page
    - [ ] upload screenshot
    - [ ] trigger “Download TSV”
    - [ ] save to `/shared/outgoing/<guild_id>/<job_id>.tsv`
    - [ ] update job `DONE` (or `FAILED` with error)
- [ ] Robustness:
    - [ ] timeouts
    - [ ] retry once on flaky UI
    - [ ] logs for selectors/downloads

**Exit criteria:** a screenshot job produces a TSV file and flips job to DONE.

---

### Phase 5 — TSV Ingestion → Snapshots

**Goal:** parse TSV and store inventory as time-series snapshots.

- [ ] Add tables:
    - [ ] `stockpiles`
    - [ ] `stockpile_snapshots` (`TIMESTAMPTZ`)
    - [ ] `snapshot_items`
- [ ] TSV parser:
    - [ ] extract `Structure Type` (from TSV)
    - [ ] map items by `CodeName`
    - [ ] parse quantity/crated/per_crate/total
- [ ] Upsert/insert flow:
    - [ ] get or create `stockpiles` row using:
        - guild_id (job)
        - town_name (job)
        - stockpile_name (job, default Public)
        - structure_type (TSV)
    - [ ] insert snapshot row
    - [ ] insert snapshot_items rows

**Exit criteria:** importing one screenshot creates a new snapshot and snapshot_items in Postgres.

---

### Phase 6 — Read Commands + Summary Output

**Goal:** users can query latest inventory and see quick answers.

- [ ] `/stockpile_latest town:<Town> stockpile_name:<optional>`
    - [ ] finds matching stockpile(s)
    - [ ] returns latest snapshot time + basic totals
- [ ] After `/import_screenshot`, bot replies with:
    - [ ] what stockpile was updated (town/structure/name)
    - [ ] number of items imported
    - [ ] “top X by priority” items for that stockpile

**Exit criteria:** data is usable in Discord without opening the database.

---

### Phase 7 — Targets & Shortage Reporting

**Goal:** turn inventory into actionable logistics signal.

- [ ] Seed `items` and `guild_item_targets`
- [ ] Add `hub_factor` + generated `min_for_hub`
- [ ] Compute shortages:
    - [ ] compare snapshot totals vs `min_total` (or base/hub logic)
    - [ ] output prioritized shortage list
- [ ] Command ideas:
    - [ ] `/needs town:<Town> stockpile_name:<optional>`
    - [ ] `/needs_near town:<Town> radius:<N>`

**Exit criteria:** bot can tell you what to deliver, prioritized.

---

### Phase 8 — UX + Ops Polish

**Goal:** make it smooth, safe, and maintainable.

- [ ] Town autocomplete in slash commands
- [ ] Better error messages (unknown town, FIR failed, parse failure)
- [ ] Cleanup old files in `/shared` after success
- [ ] Indexes for “latest snapshot” queries
- [ ] Optional admin commands:
    - [ ] `/admin seed_towns`
    - [ ] `/admin seed_items`
    - [ ] `/admin set_target ...`

**Exit criteria:** low friction for users, easy to operate on your server.

---

- Stabilize Playwright FIR automation
- Implement TSV ingestion → snapshots + items
- Add shortage reporting using `guild_item_targets`
- Add autocomplete for `town`
- Add cleanup for old job files
- Optional: explore API ingestion (FoxAPI) while keeping FIR as fallback

---

## License / Attribution

This project integrates with external tools (FIR) and follows common community conventions (e.g. item naming and
ordering).  
Hexmaster’s implementation is intended to remain **clean-room, modular, and server-side only**.
