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

1.  **Intelligence Reporting**: File reports by uploading screenshots of stockpiles.
2.  **Requisition Orders**: Compare "Shipping Hubs" against "Receiving Bases" to identify supply gaps.
3.  **Strategic Reconnaissance**: Find specific items across the entire World Conquest map with proximity sorting.
4.  **Priority Management**: Track mission-critical items through customizable priority lists.

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

## Future Roadmap

- **Dynamic Inventory Cleanup**: Automatically handle destroyed/captured towns via WarAPI.
- **Faction Tracking**: Filter inventories based on real-time faction ownership.
- **Logistics Threat Mapping**: Warn drivers if routes pass through contested territory.
- **Supply Drop Alerts**: Automated pings for low-supply frontline bases.
- **Trend Charts**: Visual graphs of stockpile changes over time.

---

## Acknowledgements & Credits

HexMaster relies on several critical community-maintained tools:

- **[Foxhole Stockpiles (FS)](https://github.com/xurxogr/foxhole-stockpiles)**: OCR and screenshot-to-data logic.
- **[WarAPI](https://github.com/clapfoot/warapi)**: Official Foxhole API for town data and map status.
- **[Discord.py](https://discordpy.readthedocs.io/)**: Discord API wrapper.
- **[SQLAlchemy](https://www.sqlalchemy.org/)**: Database abstraction.

---

## License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for the full text.

HexMaster's implementation is intended for private logistics group use and follows all community safety standards for Foxhole third-party software.
