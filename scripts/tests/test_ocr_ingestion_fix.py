import os
import sys
import unittest
import pandas as pd
from unittest.mock import AsyncMock, Mock

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src"))
)

from hexmaster.services.stockpile_service import StockpileService


class TestOCRIngestionFix(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repo = AsyncMock()
        self.ocr_service = AsyncMock()
        self.service = StockpileService(self.repo, self.ocr_service)

    async def test_process_remote_and_ingest_calculates_totals(self):
        # 1. Setup Mock OCR response
        # OCR returns placeholder 0s for Per Crate and Total
        mock_df = pd.DataFrame(
            [
                {
                    "Structure Type": "Seaport",
                    "Stockpile Name": "Public",
                    "CodeName": "BasicMaterials",
                    "Name": "Basic Materials",
                    "Quantity": 10,
                    "Crated?": "YES",
                    "Per Crate": 0,
                    "Total": 0,
                },
                {
                    "Structure Type": "Seaport",
                    "Stockpile Name": "Public",
                    "CodeName": "SoldierSupplies",
                    "Name": "Soldier Supplies",
                    "Quantity": 50,
                    "Crated?": "NO",
                    "Per Crate": 0,
                    "Total": 0,
                },
            ]
        )
        self.ocr_service.process_image.return_value = mock_df

        # 2. Setup Mock Catalog Data
        # BasicMaterials QPC = 100, SoldierSupplies QPC = 10
        self.repo.get_catalog_items.return_value = {
            "BasicMaterials": {"displayname": "Basic Materials", "qty_per_crate": 100},
            "SoldierSupplies": {"displayname": "Soldier Supplies", "qty_per_crate": 10},
        }

        # 3. Call service
        await self.service.process_remote_and_ingest(
            guild_id=123,
            image_bytes=b"fake_image",
            town="Tine",
            stockpile_name="Public",
        )

        # 4. Verify what was sent to repo.ingest_snapshot
        args, kwargs = self.repo.ingest_snapshot.call_args
        # args[5] is items
        items = args[5]

        # Verify Basic Materials (Crated)
        bm = next(i for i in items if i["code_name"] == "BasicMaterials")
        self.assertEqual(bm["quantity"], 10)
        self.assertTrue(bm["is_crated"])
        self.assertEqual(bm["per_crate"], 100)
        self.assertEqual(bm["total"], 1000)  # 10 * 100

        # Verify Soldier Supplies (Loose)
        ss = next(i for i in items if i["code_name"] == "SoldierSupplies")
        self.assertEqual(ss["quantity"], 50)
        self.assertFalse(ss["is_crated"])
        self.assertEqual(ss["per_crate"], 10)
        self.assertEqual(ss["total"], 50)  # Loose, so just quantity


if __name__ == "__main__":
    unittest.main()
