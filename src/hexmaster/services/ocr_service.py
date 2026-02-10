import io
import json
import pandas as pd
import aiohttp
from typing import Optional


class OCRServiceError(Exception):
    """Custom exception for OCR Service failures."""
    def __init__(self, status: int, message: str, technical_details: Optional[str] = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.technical_details = technical_details

    def __str__(self):
        return f"{self.message} (Status: {self.status})"


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
        data.add_field('image', image_bytes, filename='screenshot.png', content_type='image/png')
        data.add_field('town', town)
        data.add_field('label', label)

        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as resp:
                return await self._handle_response(resp)

    async def _handle_response(self, resp: aiohttp.ClientResponse) -> pd.DataFrame:
        """Internal helper to handle the OCR response."""
        if resp.status != 200:
            raw_error = await resp.text()
            try:
                error_json = json.loads(raw_error)
                msg = error_json.get("error", "Unknown OCR error")
                details = error_json.get("stderr_tail") or error_json.get("details")
                
                if "headless_process failed" in msg:
                    msg = "OCR Service encountered a headless process crash. Transient failure likely."
                
                raise OCRServiceError(resp.status, msg, details)
            except json.JSONDecodeError:
                raise OCRServiceError(resp.status, f"OCR Service returned an error: {raw_error[:200]}")

        # Assuming FIR returns a TSV or JSON that pandas can read
        content = await resp.text()
        return pd.read_csv(io.StringIO(content), sep='\t')
