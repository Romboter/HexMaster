import discord
from tabulate import tabulate

DISCORD_CHARACTER_LIMIT = 2000

async def render_and_truncate_table(
        interaction: discord.Interaction,
        rows: list[list],
        headers: list[str],
        title: str,
        ephemeral: bool = True
) -> None:
    """Renders a table with tabulate and handles Discord character limit truncation."""

    def render(data):
        return tabulate(data, headers=headers, tablefmt="simple")

    lines = render(rows)
    limit = DISCORD_CHARACTER_LIMIT - 300  # Buffer for title and code blocks

    if len(lines) > limit:
        current_rows = rows
        while len(render(current_rows)) > limit and current_rows:
            current_rows = current_rows[:-1]

        hidden_count = len(rows) - len(current_rows)
        lines = render(current_rows) + f"\n(+ {hidden_count} items hidden)"
        
    msg = f"{title}\n```\n{lines}\n```"
    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=ephemeral)
    else:
        await interaction.response.send_message(msg, ephemeral=ephemeral)
