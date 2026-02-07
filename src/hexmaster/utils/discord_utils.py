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
        as_embed: bool = False,
        color: Optional[int] = None
) -> None:
    """
    Renders a table with tabulate and handles Discord character limit truncation.
    Optionally wraps it in a Discord Embed.
    """

    def render(data):
        return tabulate(data, headers=headers, tablefmt="simple")

    # Estimate overhead
    overhead = 300 # Buffer for titles, code blocks, and "hidden" message
    limit = DISCORD_CHARACTER_LIMIT - overhead

    current_rows = rows
    lines = render(current_rows)

    if len(lines) > limit:
        # Binary search or iterative reduction? Iterative is simpler for now
        while len(render(current_rows)) > limit and current_rows:
            current_rows = current_rows[:-1]
        
        hidden_count = len(rows) - len(current_rows)
        lines = render(current_rows) + f"\n(+ {hidden_count} items hidden)"

    content = f"```\n{lines}\n```"

    if as_embed:
        embed = discord.Embed(
            title=title.replace("**", "").replace("__", ""), # Clean up markdown for embed title
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
