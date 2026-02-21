# Copyright (c) 2024-2025 Gary Kuepper
# Licensed under the MIT License.
"""Service for interacting with external OCR for image processing."""

import io
import json
from typing import Any, Optional

import aiohttp
import pandas as pd


class OCRServiceError(Exception):
    """Custom exception for OCR Service failures."""

    def __init__(
        self, status: int, message: str, technical_details: Optional[str] = None
    ) -> None:
        """Initializes the OCRServiceError."""
        super().__init__(message)
        self.status = status
        self.message = message
        self.technical_details = technical_details

    def __str__(self) -> str:
        """Returns the string representation of the error."""
        return f"{self.message} (Status: {self.status})"


class OCRService:
    """Handles communication with the external OCR container."""

    def __init__(self, base_url: str) -> None:
        """Initializes the OCRService with the base URL."""
        self.base_url = base_url

    async def process_image(
        self, image_bytes: bytes, town: str, label: str
    ) -> pd.DataFrame:
        """Sends image to the OCR service and returns a DataFrame of the results."""
        url = f"{self.base_url}/process"

        data = aiohttp.FormData()
        data.add_field(
            "image", image_bytes, filename="screenshot.png", content_type="image/png"
        )
        data.add_field("town", town)
        data.add_field("label", label)

        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as resp:
                return await self._handle_response(resp)

    async def _handle_response(self, resp: aiohttp.ClientResponse) -> pd.DataFrame:
        """Internal helper to handle the OCR response and parse content."""
        raw_content = await resp.text()

        if resp.status != 200:
            self._raise_for_status(resp.status, raw_content)

        # FIR returns a TSV that pandas can read
        return pd.read_csv(io.StringIO(raw_content), sep="\t")

    def _raise_for_status(self, status: int, raw_error: str) -> None:
        """Parses error JSON and raises OCRServiceError."""
        try:
            error_json = json.loads(raw_error)
            msg = error_json.get("error", "Unknown OCR error")
            details = error_json.get("stderr_tail") or error_json.get("details")

            if "headless_process failed" in msg:
                msg = "OCR Service encountered a headless process crash. Transient failure likely."

            raise OCRServiceError(status, msg, details)
        except json.JSONDecodeError as exc:
            raise OCRServiceError(
                status, f"OCR Service returned an error: {raw_error[:200]}"
            ) from exc
