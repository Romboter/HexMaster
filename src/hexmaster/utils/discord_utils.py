import discord
from tabulate import tabulate
from typing import Optional, List, Any

DISCORD_CHARACTER_LIMIT = 2000
EMBED_COLOR_SUCCESS = 0x2ECC71 # Green
EMBED_COLOR_ERROR = 0xE74C3C   # Red
EMBED_COLOR_INFO = 0x3498DB    # Blue

async def render_and_truncate_table(
        interaction: discord.Interaction,
        rows: List[List[Any]],
        headers: List[str],
        title: str,
        ephemeral: bool = True,
        as_embed: bool = True,
        color: Optional[int] = None
) -> None:
    """
    Renders a table using Discord Embed fields for a rich experience.
    Falls back to a code block if there are too many rows or fields.
    """
    if not rows:
        return await send_success(interaction, "No data to display.", title=title, ephemeral=ephemeral)

    # Discord limit: 25 fields per embed. 
    # If we have 3 columns, we can show ~8 rows.
    # For logistics, we often have many rows, so we might need a mix or a fallback.
    
    # Let's try to find if we can use fields for "Item", "Qty", "Status"
    num_cols = len(headers)
    max_fields = 25
    max_rows_for_fields = max_fields // num_cols

    if as_embed and len(rows) <= max_rows_for_fields:
        embed = discord.Embed(
            title=title.replace("**", "").replace("__", ""),
            color=color or EMBED_COLOR_INFO
        )
        for i, header in enumerate(headers):
            col_vals = []
            for row in rows:
                val = str(row[i])
                col_vals.append(val)
            
            embed.add_field(name=header, value="\n".join(col_vals), inline=True)
        
        await send_response(interaction, embed=embed, ephemeral=ephemeral)
    else:
        # Fallback to tabulate in a code block for larger datasets
        def render(data):
            return tabulate(data, headers=headers, tablefmt="simple")

        overhead = 300 
        limit = DISCORD_CHARACTER_LIMIT - overhead

        current_rows = rows
        lines = render(current_rows)

        if len(lines) > limit:
            while len(render(current_rows)) > limit and current_rows:
                current_rows = current_rows[:-1]
            
            hidden_count = len(rows) - len(current_rows)
            lines = render(current_rows) + f"\n(+ {hidden_count} items hidden)"

        content = f"```\n{lines}\n```"

        if as_embed:
            embed = discord.Embed(
                title=title.replace("**", "").replace("__", ""),
                description=content,
                color=color or EMBED_COLOR_INFO
            )
            await send_response(interaction, embed=embed, ephemeral=ephemeral)
        else:
            msg = f"{title}\n{content}"
            await send_response(interaction, content=msg, ephemeral=ephemeral)

async def send_response(
    interaction: discord.Interaction, 
    content: Optional[str] = None, 
    embed: Optional[discord.Embed] = None, 
    ephemeral: bool = True
) -> None:
    """Helper to handle response vs followup."""
    kwargs = {"ephemeral": ephemeral}
    if content: kwargs["content"] = content
    if embed: kwargs["embed"] = embed

    if interaction.response.is_done():
        await interaction.followup.send(**kwargs)
    else:
        await interaction.response.send_message(**kwargs)

async def send_success(interaction: discord.Interaction, message: str, title: str = "Success", ephemeral: bool = True) -> None:
    embed = discord.Embed(title=f"✅ {title}", description=message, color=EMBED_COLOR_SUCCESS)
    await send_response(interaction, embed=embed, ephemeral=ephemeral)

async def send_error(interaction: discord.Interaction, message: str, title: str = "Error", ephemeral: bool = True) -> None:
    embed = discord.Embed(title=f"❌ {title}", description=message, color=EMBED_COLOR_ERROR)
    await send_response(interaction, embed=embed, ephemeral=ephemeral)
