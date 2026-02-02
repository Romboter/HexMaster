import io
import pandas as pd
import aiohttp
from typing import Optional


class OCRService:
    def __init__(self, base_url: str):
        self.base_url = base_url

    async def process_image(self, image_bytes: bytes, town: str, label: str) -> pd.DataFrame:
        """
        Sends image to the OCR service and returns a DataFrame of the results.
        """
        # Note: Adjust the endpoint/payload based on your actual FIR container API
        url = f"{self.base_url}/process"

        data = aiohttp.FormData()
        data.add_field('file', image_bytes, filename='screenshot.png', content_type='image/png')
        data.add_field('town', town)
        data.add_field('label', label)

        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise RuntimeError(f"OCR Service returned status {resp.status}: {error_text}")

                # Assuming FIR returns a TSV or JSON that pandas can read
                content = await resp.text()
                return pd.read_csv(io.StringIO(content), sep='\t')
