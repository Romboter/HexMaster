<div align="center">
  <img src="data/core/HexMaster-cropped.png" alt="HexMaster Logo" width="200">

# HexMaster — Foxhole Logistics Discord Bot

[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)

</div>

HexMaster is a powerful Discord bot designed for **Foxhole** logistics groups. It enables seamless stockpile management, cross-map item discovery, and intelligent supply chain comparison using OCR and real-time game data.

The bot follows a **snapshot-based storage** model, preserving full historical data of every stockpile update without ever overwriting.

---

## Documentation Links 📚

- **[Installation & Deployment](docs/installation.md)**: Setup guides for Docker and local development.
- **[User Guide (Commands)](docs/commands.md)**: Detailed info on `/report`, `/locate`, `/inventory`, and more.
- **[Admin Guide (Tools)](docs/admin.md)**: How to configure the bot, shards, and priority lists.
- **[Technical Reference](docs/tech_reference.md)**: Architecture, project structure, and technical details.

---

## What HexMaster Does

1. **Intelligence Reporting**: File reports by uploading screenshots of stockpiles.
2. **Requisition Orders**: Compare "Shipping Hubs" against "Receiving Bases" to identify supply gaps.
3. **Strategic Reconnaissance**: Find specific items across the entire World Conquest map with proximity sorting.
4. **Priority Management**: Track mission-critical items through customizable priority lists.

---

## Quick Reference 🚀

### For Players

- `/report`: Upload a screenshot to update stockpile data.
- `/locate`: Find the nearest source of a specific item.
- `/inventory`: View items currently held in a town or base.
- `/requisition`: Calculate what supplies are missing from a destination.

### For Admins

- `/setup config`: Set your server's faction and shard.
- `/setup priorities`: Load standard priority templates.

---

---

## Acknowledgements & Credits

HexMaster relies on several critical community-maintained tools:

- **[Foxhole Stockpiles (FS)](https://github.com/xurxogr/foxhole-stockpiles)**: OCR and screenshot-to-data logic.
- **[WarAPI](https://github.com/clapfoot/warapi)**: Official Foxhole API for town data and map status.
- **[Discord.py](https://discordpy.readthedocs.io/)**: Discord API wrapper.
- **[SQLAlchemy](https://www.sqlalchemy.org/)**: Database abstraction.

---

## Future Roadmap

While the core logic is now stable, the following UI and feature enhancements are planned:

- **Dynamic Inventory Cleanup**: Automatically remove or "grey out" inventories for Seaports or Storage Warehouses that the WarAPI reports as **Destroyed** or **Captured** by the enemy.
- **Faction Tracking**: Only show inventories that belong to the bot-owner's faction (Colonials/Wardens) in real-time.
- **Logistics Threat Mapping**: Overlay current "Front Line" map data to warn logistics drivers if a `/locate` result requires driving through contested or enemy-held territory.
- **Supply Drop Alerts**: Automated pings when a critical frontline base (based on WarAPI status) is low on Soldier Supplies or AT weapons.
- **Trend Charts**: Visual graphs of stockpile changes over the last 24-48 hours.

---

## Acknowledgements & Credits

HexMaster relies on several critical community-maintained tools:

- **[Foxhole Stockpiles (FS)](https://github.com/xurxogr/foxhole-stockpiles)**: OCR and screenshot-to-data logic.
- **[WarAPI](https://github.com/clapfoot/warapi)**: Official Foxhole API for town data and map status.
- **[Discord.py](https://discordpy.readthedocs.io/)**: Discord API wrapper.
- **[SQLAlchemy](https://www.sqlalchemy.org/)**: Database abstraction.

---

## Technical Reference

- **Bot Implementation**: `src/hexmaster/bot/main.py`
- **Database Schema**: `src/hexmaster/db/models.py`
- **Reference Data**: Located in `data/` (Towns, Regions, Catalog)

---

## License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for the full text.

HexMaster's implementation is intended for private logistics group use and follows all community safety standards for Foxhole third-party software.
