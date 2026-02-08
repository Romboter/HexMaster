import discord
from tabulate import tabulate
from typing import Optional, List, Any

DISCORD_CHARACTER_LIMIT = 2000
EMBED_COLOR_SUCCESS = 0x2ECC71 # Green
EMBED_COLOR_ERROR = 0xE74C3C   # Red
EMBED_COLOR_INFO = 0x3498DB    # Blue

class PaginatorView(discord.ui.View):
    def __init__(
        self, 
        pages: List[str], 
        title: str, 
        color: int, 
        ephemeral: bool,
        interaction: discord.Interaction
    ):
        super().__init__(timeout=300)
        self.pages = pages
        self.title = title
        self.color = color
        self.ephemeral = ephemeral
        self.interaction = interaction
        self.current_page = 0
        
        # Update button states
        self.update_buttons()

    def update_buttons(self):
        self.previous_button.disabled = (self.current_page == 0)
        self.next_button.disabled = (self.current_page == len(self.pages) - 1)

    async def update_message(self, interaction: discord.Interaction):
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    def create_embed(self) -> discord.Embed:
        page_indicator = f" (Page {self.current_page + 1}/{len(self.pages)})" if len(self.pages) > 1 else ""
        embed = discord.Embed(
            title=f"{self.title}{page_indicator}",
            description=f"```ansi\n{self.pages[self.current_page]}\n```",
            color=self.color
        )
        return embed

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.gray)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        self.update_buttons()
        await self.update_message(interaction)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.gray)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        self.update_buttons()
        await self.update_message(interaction)


async def render_and_truncate_table(
        interaction: discord.Interaction,
        rows: List[List[Any]],
        headers: List[str],
        title: str,
        ephemeral: bool = True,
        as_embed: bool = True,
        color: Optional[int] = None,
        row_colors: Optional[List[str]] = None,
        max_rows: int = 20
) -> None:
    """
    Renders a table using ANSI colors in a monospaced code block with pagination.
    max_rows: Maximum rows per page (default 20).
    """
    if not rows:
        return await send_success(interaction, "No data to display.", title=title, ephemeral=ephemeral)

    # Discord Description Limit is 4096. 
    # Use 3800 to be safe with code block markers and titles.
    DESC_LIMIT = 3800

    # Tabulate everything once to get consistent column widths
    full_table_str = tabulate(rows, headers=headers, tablefmt="simple")
    lines = full_table_str.split("\n")
    header_lines = lines[:2]
    data_lines = lines[2:]

    header_str = "\n".join([f"\u001b[1;37m{l}\u001b[0m" for l in header_lines]) + "\n"
    
    pages = []
    current_page_lines = []
    current_len = len(header_str)
    current_row_count = 0
    
    for i, line in enumerate(data_lines):
        # Apply color logic
        colored_line = line
        if row_colors and i < len(row_colors) and row_colors[i]:
            colored_line = f"\u001b[0;{row_colors[i]}m{line}\u001b[0m"
            
        line_len = len(colored_line) + 1 # +1 for newline
        
        # Check if we should start a new page (character limit OR row limit)
        should_split = False
        if current_page_lines:
            if current_len + line_len > DESC_LIMIT:
                should_split = True
            elif current_row_count >= max_rows:
                should_split = True

        if should_split:
            pages.append(header_str + "\n".join(current_page_lines))
            current_page_lines = [colored_line]
            current_len = len(header_str) + line_len
            current_row_count = 1
        else:
            current_page_lines.append(colored_line)
            current_len += line_len
            current_row_count += 1
            
    if current_page_lines:
        pages.append(header_str + "\n".join(current_page_lines))

    target_color = color or EMBED_COLOR_INFO

    if as_embed:
        view = None
        if len(pages) > 1:
            view = PaginatorView(pages, title, target_color, ephemeral, interaction)
            embed = view.create_embed()
        else:
            embed = discord.Embed(
                title=title.replace("**", "").replace("__", ""),
                description=f"```ansi\n{pages[0]}\n```",
                color=target_color
            )
        
        await send_response(interaction, embed=embed, view=view, ephemeral=ephemeral)
    else:
        # Fallback for non-embed (rarely used here)
        msg = f"**{title}**\n```ansi\n{pages[0]}\n```"
        if len(pages) > 1:
            msg += f"\n*(Showing page 1/{len(pages)} - use embed view for pagination)*"
        await send_response(interaction, content=msg, ephemeral=ephemeral)

async def send_response(
    interaction: discord.Interaction, 
    content: Optional[str] = None, 
    embed: Optional[discord.Embed] = None, 
    view: Optional[discord.ui.View] = None,
    ephemeral: bool = True
) -> None:
    """Helper to handle response vs followup."""
    kwargs = {"ephemeral": ephemeral}
    if content: kwargs["content"] = content
    if embed: kwargs["embed"] = embed
    if view: kwargs["view"] = view

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
