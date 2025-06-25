import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import sys
import os

# Add the project directory to the path so we can import the modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from specfic_home_info_helper import bootstrap_price_histories
from dataBase import Price_History


class TestBootstrapPriceHistories(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.mock_session = Mock()
        self.listing_id = 123
        
    def create_price_history_entry(self, date, description, price):
        """Helper method to create a price history entry."""
        return {
            "date": date,
            "description": description,
            "price": price
        }

    
    def test_empty_price_history(self):
        """Test behavior with empty price history."""
        price_history = []
        
        with patch('specfic_home_info_helper.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 6, 1)
            mock_datetime.strptime = datetime.strptime
            
            bootstrap_price_histories(self.listing_id, price_history, self.mock_session)
        
        # Should not add any price history records
        self.assertEqual(self.mock_session.add.call_count, 0)
    

    def test_session_flush_called(self):
        """Test that session.flush() is called after processing."""
        price_history = [
            self.create_price_history_entry("2025-02-14", "Listed (Active)", 1149000),
            self.create_price_history_entry("2025-02-27", "Price Changed", 1099900),
        ]
        
        with patch('specfic_home_info_helper.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 6, 1)
            mock_datetime.strptime = datetime.strptime
            
            bootstrap_price_histories(self.listing_id, price_history, self.mock_session)
        
        # Verify flush was called
        self.mock_session.flush.assert_called_once()

    def test_realistic_redfin_scenario(self):
        """Test the scenario described by the user with relisting and price changes after a Sold event."""
        price_history = [
            self.create_price_history_entry("2009-01-23", "Listed", 350000),
            self.create_price_history_entry("2009-06-11", "Listing Removed", None),
            self.create_price_history_entry("2009-08-24", "Sold (MLS)", 325000),
            self.create_price_history_entry("2025-02-14", "Listed (Active)", 1149000),
            self.create_price_history_entry("2025-02-27", "Price Changed", 1099900),
            self.create_price_history_entry("2025-03-28", "Listing Removed", None),
            self.create_price_history_entry("2025-05-22", "Listed (Active)", 999900),
        ]

        with patch('specfic_home_info_helper.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 6, 1)
            mock_datetime.strptime = datetime.strptime

            bootstrap_price_histories(self.listing_id, price_history, self.mock_session)

        # Should only create 3 records:
        # null -> 1,149,000 (Feb 14, 2025)
        # 1,149,000 -> 1,099,900 (Feb 27, 2025)
        # 1,099,900 -> 999,900 (May 22, 2025)
        self.assertEqual(self.mock_session.add.call_count, 3)

        calls = self.mock_session.add.call_args_list
        # First transition
        first = calls[0][0][0]
        self.assertEqual(first.old_price, None)
        self.assertEqual(first.new_price, 1149000)
        self.assertEqual(first.change_date, "2025-02-14")
        # Second transition
        second = calls[1][0][0]
        self.assertEqual(second.old_price, 1149000)
        self.assertEqual(second.new_price, 1099900)
        self.assertEqual(second.change_date, "2025-02-27")
        # Third transition
        third = calls[2][0][0]
        self.assertEqual(third.old_price, 1099900)
        self.assertEqual(third.new_price, 999900)
        self.assertEqual(third.change_date, "2025-05-22")

    def test_single_listing_after_sold(self):
        """Test scenario with only one listing event after the most recent sold event."""
        price_history = [
            self.create_price_history_entry("2001-11-29", "Sold (Public Records)", 197768),
            self.create_price_history_entry("2010-09-08", "Listed (Active)", 365000),
            self.create_price_history_entry("2010-11-05", "Price Changed", 360000),
            self.create_price_history_entry("2011-01-03", "Price Changed", 350000),
            self.create_price_history_entry("2011-02-09", "Price Changed", 344900),
            self.create_price_history_entry("2011-04-15", "Listing Removed", None),
            self.create_price_history_entry("2025-06-12", "Listed (Active)", 710000),
        ]

        with patch('specfic_home_info_helper.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 6, 15)
            mock_datetime.strptime = datetime.strptime

            bootstrap_price_histories(self.listing_id, price_history, self.mock_session)

        # Should only create 1 record: null -> 710,000 (Jun 12, 2025)
        self.assertEqual(self.mock_session.add.call_count, 1)

        call = self.mock_session.add.call_args_list[0][0][0]
        self.assertEqual(call.old_price, None)
        self.assertEqual(call.new_price, 710000)
        self.assertEqual(call.change_date, "2025-06-12")

   

if __name__ == '__main__':
    unittest.main()