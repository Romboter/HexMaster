import unittest
from unittest.mock import AsyncMock, Mock
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from hexmaster.services.stockpile_service import StockpileService

class TestStockpileServiceRequisition(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repo = AsyncMock()
        self.ocr_service = Mock()
        self.war_service = Mock()
        self.service = StockpileService(self.repo, self.ocr_service, self.war_service)

    async def test_requisition_hub_to_hub(self):
        # Setup Mocks
        guild_id = 123
        ship_town = "Seaport A"
        recv_town = "Seaport B"
        
        # Priority items
        self.repo.get_priority_list.return_value = [
            {"codename": "C1", "name": "Item1", "qty_per_crate": 10, "min_for_base_crates": 5, "priority": 1}
        ]
        
        # Snapshots: Hub to Hub
        ship_snap = {"struct_type": "Seaport", "captured_at": "now"}
        recv_snap = {"struct_type": "Seaport", "captured_at": "now"}
        
        # Ship has 100 loose C1 (10 crates worth) and 50 crated C1 (5 crates worth)
        ship_items = [
            {"code_name": "C1", "item_name": "Item1", "total": 100, "is_crated": False, "catalog_qpc": 10, "per_crate": 10},
            {"code_name": "C1", "item_name": "Item1", "total": 50, "is_crated": True, "catalog_qpc": 10, "per_crate": 10},
        ]
        
        # Recv has 0 C1
        recv_items = []
        
        self.repo.get_latest_snapshot_for_town_filtered.side_effect = [
            (ship_snap, ship_items),
            (recv_snap, recv_items)
        ]
        
        result = await self.service.get_requisition_comparison(guild_id, ship_town, recv_town)
        
        data = result["comparison_data"]
        # Expecting 2 entries for Item1: one for Craters, one for Loose
        self.assertEqual(len(data), 2)
        
        crated_entry = next(d for d in data if d["is_crated"] is True)
        self.assertEqual(crated_entry["Avail"], 5.0) 
        
        loose_entry = next(d for d in data if d["is_crated"] is False)
        self.assertEqual(loose_entry["Avail"], 10.0)

    async def test_requisition_hub_to_base(self):
        # Setup Mocks
        guild_id = 123
        ship_town = "Seaport A"
        recv_town = "Base B"
        
        # Priority items
        self.repo.get_priority_list.return_value = [
            {"codename": "C1", "name": "Item1", "qty_per_crate": 10, "min_for_base_crates": 5, "priority": 1}
        ]
        
        # Snapshots: Hub to Base
        ship_snap = {"struct_type": "Seaport", "captured_at": "now"}
        recv_snap = {"struct_type": "Relic Base", "captured_at": "now"}
        
        # Ship has 100 loose C1 (10 crates worth) and 50 crated C1 (5 crates worth)
        ship_items = [
            {"code_name": "C1", "item_name": "Item1", "total": 100, "is_crated": False, "catalog_qpc": 10, "per_crate": 10},
            {"code_name": "C1", "item_name": "Item1", "total": 50, "is_crated": True, "catalog_qpc": 10, "per_crate": 10},
        ]
        
        # Recv has 0 C1
        recv_items = []
        
        self.repo.get_latest_snapshot_for_town_filtered.side_effect = [
            (ship_snap, ship_items),
            (recv_snap, recv_items)
        ]
        
        result = await self.service.get_requisition_comparison(guild_id, ship_town, recv_town)
        
        data = result["comparison_data"]
        # Expecting ONLY 1 entry for Item1 (Crated only), ignoring loose
        self.assertEqual(len(data), 1)
        self.assertTrue(data[0]["is_crated"])
        self.assertEqual(data[0]["Avail"], 5.0)

if __name__ == '__main__':
    unittest.main()
