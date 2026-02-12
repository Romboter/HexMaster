# Technical Reference

This document provides a deeper look into the architecture and implementation of HexMaster.

## Architecture

HexMaster is built with a modular approach to handle Discord interactions, database persistence, and external API sync.

- **Discord Bot**: Built with `discord.py` for handling slash commands and interactions.
- **Database**: PostgreSQL with `SQLAlchemy` and `asyncpg` for asynchronous database operations.
- **Sync Logic**: Standalone Python scripts for seeding regions and syncing with the Foxhole WarAPI.
- **OCR Integration**: Communicates with the [Foxhole Stockpiles](https://github.com/xurxogr/foxhole-stockpiles) service for image processing.

## Project Structure

- **Bot Implementation**: [src/hexmaster/bot/main.py](file:///home/flynn/HexMaster/src/hexmaster/bot/main.py)
- **Database Schema**: [src/hexmaster/db/schema.sql](file:///home/flynn/HexMaster/src/hexmaster/db/schema.sql) (managed automatically)
- **Reference Data**: [data/](file:///home/flynn/HexMaster/data/) (Contains Towns, Regions, and the Item Catalog)
- **Scripts**: [scripts/](file:///home/flynn/HexMaster/scripts/) (Utilities for data syncing and seeding)

## Snapshot Model

HexMaster uses a **snapshot-based storage** model. Every stockpile report creates a new time-stamped record. This ensures that historical data is preserved and allows for trend analysis without losing previous state.

## Coordinate System

The bot uses a **Cartesian-Staggered** coordinate system to map Foxhole's hex-based world into a 2D plane. This allows for accurate distance calculations (in hex units) between towns across different regions.
