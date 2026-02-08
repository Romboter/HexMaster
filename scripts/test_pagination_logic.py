import asyncio
from unittest.mock import MagicMock, AsyncMock
import sys
import os

# Add src to path at the beginning to ensure local source is used
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from hexmaster.utils.discord_utils import render_and_truncate_table

async def test_pagination():
    print("Running pagination logic test...")
    
    # Mock interaction
    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    interaction.response.is_done.return_value = False
    
    # 50 rows, should split into 20, 20, 10 (3 pages)
    headers = ["Col1", "Col2"]
    rows = [[f"R{i}", f"V{i}"] for i in range(1, 51)]
    title = "Test Paging"
    
    # We need to capture the 'pages' variable from inside the function
    # Since it's not returned, we might need a small refactor or just trust the logic
    # BUT, we can check the 'view' passed to send_response if we can intercept it.
    
    # Let's wrap send_response to capture the view
    import hexmaster.utils.discord_utils as du
    captured_pages = []
    
    async def mock_send_response(inter, content=None, embed=None, view=None, ephemeral=True):
        if view:
            captured_pages.extend(view.pages)
        elif embed and embed.description:
            # If only 1 page, it won't have a view in the current impl if pages len is 1
            # But here we expect 3 pages.
            pass

    du.send_response = AsyncMock(side_effect=mock_send_response)
    
    await render_and_truncate_table(interaction, rows, headers, title, max_rows=20)
    
    print(f"Captured {len(captured_pages)} pages.")
    for i, p in enumerate(captured_pages):
        # Subtract 2 for header lines
        line_count = len(p.strip().split("\n")) - 2 
        print(f"Page {i+1} line count (data): {line_count}")
        
    assert len(captured_pages) == 3, f"Expected 3 pages, got {len(captured_pages)}"
    assert "R1" in captured_pages[0]
    assert "R20" in captured_pages[0]
    assert "R21" in captured_pages[1]
    assert "R40" in captured_pages[1]
    assert "R41" in captured_pages[2]
    assert "R50" in captured_pages[2]
    
    print("✅ Pagination logic test passed!")

if __name__ == "__main__":
    asyncio.run(test_pagination())
