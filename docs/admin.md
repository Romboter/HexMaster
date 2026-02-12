# Admin Guide: HexMaster Configuration

Administrator permissions are required to run these commands.

## Setup Commands

| Command             | Description                                         |
| ------------------- | --------------------------------------------------- |
| `/setup config`     | **Configure Server** settings (Faction, Shard).     |
| `/setup priorities` | **Load Priority Templates** or clear existing ones. |
| `/priority add`     | **Add/Update Item** in the priority list.           |
| `/priority remove`  | **Remove Item** from the priority list.             |

---

## Initial Setup

Once HexMaster is invited to your server, follow these steps:

1.  **Configure Faction & Shard**
    Run `/setup config faction:[Colonial/Warden] shard:[Alpha/Bravo/Charlie]`.
    - This tells the bot which WarAPI endpoint to use and which faction-specific items to track.

2.  **Initialize Priorities**
    Run `/setup priorities template:standard` to load a default list of 60+ critical logistics items.
    - This helps the `/requisition` command know what items are essential.

## Customizing Priorities

You can fine-tune your priority list based on current war objectives:

- **Add Item**: `/priority add item_name:[Item] amount:[Target]`
- **Remove Item**: `/priority remove item_name:[Item]`

---

## Permissions

Ensure the bot has permissions to:

- Use Slash Commands
- Embed Links
- Attach Files (for report analysis)
- Read Message History
