# Hexmaster — Foxhole Logistics Discord Bot

Hexmaster is a Discord bot for **Foxhole** logistics groups. It tracks **stockpile inventory over time** using **snapshot-based storage** (no overwriting), so you can see changes and trends per town/stockpile across days.

It runs on your server via **Docker Compose**, is written in **Python (discord.py 2.x)**, and uses **PostgreSQL** for persistence. Inventory transcription is performed by **FIR (Foxhole Inventory Report)** using screenshot → TSV export, driven by a headless worker (Playwright).

---

## What Hexmaster Does (MVP)

- Accepts **one stockpile screenshot per import** via a Discord slash command.
- Queues an `import_jobs` record in Postgres.
- A worker processes the screenshot through FIR and produces a **TSV** file.
- The bot ingests the TSV into Postgres as a **new snapshot** (time-series).
- Supports **multiple Discord guilds** (multi-tenant) via `guild_id`.

---

## Architecture

### Services (Docker Compose)

- `hexmaster_bot`
  - discord.py bot
  - SQLAlchemy async + asyncpg
  - Creates DB tables on startup
- `postgres`
  - Stores all bot data
- `fir`
  - FIR website (screenshot processing + export)
- `fir_worker`
  - Playwright automation:
    - uploads screenshot to FIR
    - clicks “Download TSV”
    - saves TSV to shared volume
    - marks job DONE/FAILED

### Shared volume layout

The bot and worker share a filesystem volume:

- Incoming screenshots:
  - `/shared/incoming/<guild_id>/<job_id>/<filename>.png`
- Outgoing TSV results:
  - `/shared/outgoing/<guild_id>/<job_id>.tsv`

---

## FIR TSV Format (Observed)

FIR exports a TSV with the following header columns:

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

Example row:

- `Structure Type`: `Seaport`
- `Crated?`: `TRUE`
- `CodeName`: e.g. `SoldierSupplies`

Hexmaster uses:
- `Structure Type` from TSV (no user input)
- `CodeName` as the primary item key (maps to `items.code_name`)

---

## Discord Commands

### `/ping`
Health check + DB connectivity test.

### `/import_screenshot town:<Town> stockpile_name:<optional> image:<attachment>`
Imports one screenshot.

Rules:
- `town` required and validated against `towns` table
- `stockpile_name` defaults to `Public` if omitted/blank
- the bot queues a job; ingestion occurs after FIR worker finishes

### `/stockpile_latest town:<Town> stockpile_name:<optional>`
Shows the latest snapshot metadata (summary output is expanded after TSV ingestion is implemented).

---

## Database Overview

Global reference (shared across all guilds):
- `regions`
- `towns`
- `items` (keyed by `code_name`)

Guild-scoped (isolated by `guild_id`):
- `guilds`
- `guild_item_targets`
- `stockpiles` (unique: guild + town + structure + stockpile_name)
- `stockpile_snapshots`
- `snapshot_items`
- `import_jobs`

All timestamps use Postgres `TIMESTAMPTZ`.

---

## Getting Started

### 1) Requirements

- Docker + Docker Compose
- A Discord bot token (set `DISCORD_TOKEN`)
- (Recommended) A populated `towns` table (otherwise imports will be rejected)

### 2) Configure environment

Create a `.env` file (example):
