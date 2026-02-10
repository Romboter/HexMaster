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
        self.base_url = base_url.rstrip('/')

    async def process_image(self, image_bytes: bytes, town: str = None, label: str = None) -> pd.DataFrame:
        """
        Sends image to the Foxhole Stockpiles (FS) service and returns a DataFrame.
        """
        # FS typically listens on /ocr/scan_image
        url = f"{self.base_url}/ocr/scan_image"

        data = aiohttp.FormData()
        # FS expects the file field to be named 'image'
        data.add_field('image', image_bytes, filename='screenshot.png', content_type='image/png')
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, data=data) as resp:
                    return await self._handle_response(resp, town, label)
            except aiohttp.ClientError as e:
                raise OCRServiceError(500, f"Connection to FS Service failed: {str(e)}")

    async def _handle_response(self, resp: aiohttp.ClientResponse, fallback_town: str, fallback_label: str) -> pd.DataFrame:
        """Internal helper to handle the FS JSON response."""
        if resp.status != 200:
            raw_text = await resp.text()
            raise OCRServiceError(resp.status, f"FS Service returned error: {raw_text[:200]}")

        try:
            data = await resp.json()
        except Exception:
            raise OCRServiceError(resp.status, "Failed to decode JSON response from FS.")

        if not isinstance(data, dict):
            return pd.DataFrame()

        # FS JSON Structure:
        # { "name": "...", "type": "...", "items": [...] }
        # Sometimes nested under 'stockpile' key
        stockpile_data = data.get('stockpile')
        # Robust check: if 'stockpile' exists but is None, or doesn't exist, use 'data'
        if not isinstance(stockpile_data, dict):
            stockpile_data = data
        
        # Extract Metadata
        detected_name = stockpile_data.get('name')
        detected_type = stockpile_data.get('type')
        
        final_stockpile_name = detected_name if detected_name else fallback_label
        final_struct_type = detected_type if detected_type else "Unknown"

        items = stockpile_data.get('items', [])
        if not items and "items" not in stockpile_data:
            # Maybe the whole 'data' was a list after all? 
            # (Though we checked generic dict above)
            pass

        # Convert to DataFrame matching the specific columns StockpileService expects
        rows = []
        for item in items:
            if not isinstance(item, dict): continue
            code = item.get('code')
            if not code: continue
            
            rows.append({
                "Structure Type": final_struct_type,
                "Stockpile Name": final_stockpile_name,
                "CodeName": code,
                "Name": code,
                "Quantity": item.get('quantity', 0),
                "Crated?": "YES" if item.get('crated') else "NO",
                "Per Crate": 0,
                "Total": 0,
                "Description": ""
            })

        return pd.DataFrame(rows)
