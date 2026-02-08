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
        color: Optional[int] = None,
        row_colors: Optional[List[str]] = None
) -> None:
    """
    Renders a table using ANSI colors in a monospaced code block.
    row_colors: List of ANSI color codes (e.g., "31" for red, "32" for green)
    """
    if not rows:
        return await send_success(interaction, "No data to display.", title=title, ephemeral=ephemeral)

    def render(data, is_ansi=False):
        table_str = tabulate(data, headers=headers, tablefmt="simple")
        if not is_ansi:
            return table_str
        
        # Split into lines to apply colors
        lines = table_str.split("\n")
        # lines[0] is headers, lines[1] is separator, lines[2:] are data
        header_lines = lines[:2]
        data_lines = lines[2:]
        
        colored_lines = []
        # Bold headers
        for line in header_lines:
            colored_lines.append(f"\u001b[1;37m{line}\u001b[0m")
            
        for i, line in enumerate(data_lines):
            if row_colors and i < len(row_colors) and row_colors[i]:
                colored_lines.append(f"\u001b[0;{row_colors[i]}m{line}\u001b[0m")
            else:
                colored_lines.append(line)
        
        return "\n".join(colored_lines)

    # Estimate overhead for ANSI blocks
    # ANSI blocks add ~15 chars per row. 
    overhead = 400 
    limit = DISCORD_CHARACTER_LIMIT - overhead

    current_rows = rows
    # Truncation logic uses raw length (without ANSI codes) for simplicity,
    # then we wrap it.
    while len(tabulate(current_rows, headers=headers, tablefmt="simple")) > limit and current_rows:
        current_rows = current_rows[:-1]

    ansi_content = render(current_rows, is_ansi=True)
    if len(current_rows) < len(rows):
        hidden_count = len(rows) - len(current_rows)
        ansi_content += f"\n\u001b[0;33m(+ {hidden_count} items hidden)\u001b[0m"

    content = f"```ansi\n{ansi_content}\n```"

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
