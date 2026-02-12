# User Guide: HexMaster Commands

HexMaster provides several commands for stockpile management and reconnaissance.

## Command List

| Command          | Description                                                           |
| ---------------- | --------------------------------------------------------------------- |
| `/report`        | **File an Intelligence Report** by uploading a stockpile screenshot.  |
| `/inventory`     | **View the Inventory** for a specific town or base.                   |
| `/locate`        | **Perform Reconnaissance** to find an item's location across the map. |
| `/requisition`   | **Calculate a Requisition Order** to identify supply gaps.            |
| `/priority list` | **View the Priority List** for your current server.                   |
| `/help`          | Display the command list and lore.                                    |

---

## Command Details

### `/report`

Upload a screenshot of a Foxhole stockpile (Seaport, Warehouse, or Base). HexMaster's OCR will process the items and update the database.

- **Tip**: Ensure the screenshot is clear and includes the item icons and quantities.

### `/inventory`

Check the current stock of a specific location.

- **Parameters**: `location` (Town or Base name).
- **Behavior**: Shows a list of crates and loose items available in that stockpile based on the latest report.

### `/locate`

Search for a specific item across all tracked stockpiles.

- **Parameters**: `item_name` and `reference_location`.
- **Behavior**: Sorts results by distance from the reference location, helping you find the nearest supply source.

### `/requisition`

Compare two stockpiles to see what's needed.

- **Parameters**: `hub` (Source) and `base` (Destination).
- **Behavior**: Highlights shortages and standardizes quantities into crates. It automatically applies a 4x multiplier for hubs like Seaports.

### `/priority list`

Displays the list of items prioritized by your server admins. Useful for knowing what to focus on during logistics runs.

### `/help`

Provides a quick reference to all commands and a bit of lore about the bot.
