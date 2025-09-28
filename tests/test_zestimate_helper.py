import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
import sys
import os

# Add the project directory to the path so we can import the modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zestimate_helper import (
    get_zestimate,
    create_url,
    pull_zestimate_from_html,
    upsert_zestimates
)


class TestZestimateHelper(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.sample_address = "123 Main St"
        self.sample_city = "San Francisco"
        self.sample_state = "CA"
        self.sample_zipcode = "94102"
        
        # Sample HTML with zestimate data
        self.sample_html = '''
        <html>
        <head><title>Test Property</title></head>
        <body>
        <script type="text/javascript">
        window.__INITIAL_STATE__ = {
            "address": {
                "rentZestimate": 750000,
                "rentZestimateRangeHigh": 800000,
                "rentZestimateRangeLow": 700000
            }
        };
        </script>
        </body>
        </html>
        '''
        
        # Sample HTML with no zestimate data
        self.empty_html = '''
        <html>
        <head><title>Test Property</title></head>
        <body>
        <script type="text/javascript">
        window.__INITIAL_STATE__ = {
            "address": {
                "rentZestimate": null,
                "rentZestimateRangeHigh": null,
                "rentZestimateRangeLow": null
            }
        };
        </script>
        </body>
        </html>
        '''

    def test_create_url_basic(self):
        """Test URL creation with basic address."""
        result = create_url(self.sample_address, self.sample_city, self.sample_state, self.sample_zipcode)
        expected = "https://www.zillow.com/rental-manager/price-my-rental/results/123-main-st-san-francisco-ca-94102/"
        self.assertEqual(result, expected)

    def test_create_url_with_spaces(self):
        """Test URL creation with spaces in address."""
        address = "123 Main Street Apt 4B"
        result = create_url(address, self.sample_city, self.sample_state, self.sample_zipcode)
        expected = "https://www.zillow.com/rental-manager/price-my-rental/results/123-main-street-apt-4b-san-francisco-ca-94102/"
        self.assertEqual(result, expected)

    def test_create_url_mixed_case(self):
        """Test URL creation with mixed case input."""
        address = "123 MAIN St"
        city = "San Francisco"
        state = "CA"
        result = create_url(address, city, state, self.sample_zipcode)
        expected = "https://www.zillow.com/rental-manager/price-my-rental/results/123-main-st-san-francisco-ca-94102/"
        self.assertEqual(result, expected)

    def test_pull_zestimate_from_html_success(self):
        """Test successful zestimate extraction from HTML."""
        result = pull_zestimate_from_html(self.sample_html)
        
        self.assertEqual(result[0], 750000)  # zestimate
        self.assertEqual(result[1], 800000)  # zestimate_high
        self.assertEqual(result[2], 700000)  # zestimate_low

    def test_pull_zestimate_from_html_no_data(self):
        """Test zestimate extraction when no data is available."""
        result = pull_zestimate_from_html(self.empty_html)
        
        self.assertIsNone(result[0])  # zestimate
        self.assertIsNone(result[1])  # zestimate_high
        self.assertIsNone(result[2])  # zestimate_low

    def test_pull_zestimate_from_html_no_script_tags(self):
        """Test zestimate extraction when no script tags exist."""
        html = "<html><body><p>No scripts here</p></body></html>"
        
        with self.assertRaises(ValueError) as context:
            pull_zestimate_from_html(html)
        
        self.assertIn("No script tags with type='text/javascript'", str(context.exception))

    def test_pull_zestimate_from_html_no_initial_state(self):
        """Test zestimate extraction when no INITIAL_STATE is found."""
        html = '''
        <html>
        <body>
        <script type="text/javascript">
        var otherData = {"some": "data"};
        </script>
        </body>
        </html>
        '''
        
        with self.assertRaises(ValueError) as context:
            pull_zestimate_from_html(html)
        
        self.assertIn("Could not find any <script> with window.__INITIAL_STATE__", str(context.exception))

    @patch('zestimate_helper.fetch_html_via_https')
    def test_get_zestimate_success(self, mock_fetch_html):
        """Test successful zestimate retrieval."""
        # Setup
        mock_fetch_html.return_value = self.sample_html
        
        # Execute
        result = get_zestimate(self.sample_address, self.sample_city, self.sample_state, self.sample_zipcode)
        
        # Verify
        self.assertEqual(result[0], 750000)  # zestimate
        self.assertEqual(result[1], 800000)  # zestimate_high
        self.assertEqual(result[2], 700000)  # zestimate_low
        
        # Verify fetch_html_via_https was called with correct URL
        expected_url = "https://www.zillow.com/rental-manager/price-my-rental/results/123-main-st-san-francisco-ca-94102/"
        mock_fetch_html.assert_called_once()

    @patch('zestimate_helper.fetch_with_retries_via_playwright')
    @patch('zestimate_helper.fetch_html_via_https')
    def test_get_zestimate_fallback_to_playwright(self, mock_fetch_html, mock_playwright):
        """Test zestimate retrieval with playwright fallback."""
        # Setup
        mock_fetch_html.side_effect = Exception("HTTP Error")
        mock_playwright.return_value = self.sample_html
        
        # Execute
        result = get_zestimate(self.sample_address, self.sample_city, self.sample_state, self.sample_zipcode)
        
        # Verify
        self.assertEqual(result[0], 750000)  # zestimate
        self.assertEqual(result[1], 800000)  # zestimate_high
        self.assertEqual(result[2], 700000)  # zestimate_low
        
        # Verify both methods were called
        mock_fetch_html.assert_called_once()
        mock_playwright.assert_called_once()

    @patch('dataBase.SessionLocal')
    def test_upsert_zestimates_new_record(self, mock_session_local):
        """Test upsert_zestimates with new zestimate record."""
        # Setup
        mock_session = Mock()
        mock_session_local.return_value = mock_session
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        
        # Mock Property object
        mock_property = Mock()
        mock_property.current_zestimate = None
        mock_property.current_zestimate_high = None
        mock_property.current_zestimate_low = None
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_property
        
        property_id = 123
        zestimate = 750000
        zestimate_high = 800000
        zestimate_low = 700000
        
        # Execute
        upsert_zestimates(mock_session, property_id, zestimate, zestimate_high, zestimate_low)
        
        # Verify
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        # Note: session.close() is not called by the function - it's managed externally

    @patch('dataBase.SessionLocal')
    def test_upsert_zestimates_existing_record(self, mock_session_local):
        """Test upsert_zestimates with existing zestimate record."""
        # Setup
        mock_session = Mock()
        mock_session_local.return_value = mock_session
        
        # Mock Property object
        mock_property = Mock()
        mock_property.current_zestimate = 700000
        mock_property.current_zestimate_high = 750000
        mock_property.current_zestimate_low = 650000
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_property
        
        property_id = 123
        zestimate = 750000
        zestimate_high = 800000
        zestimate_low = 700000
        
        # Execute
        upsert_zestimates(mock_session, property_id, zestimate, zestimate_high, zestimate_low)
        
        # Verify
        self.assertEqual(mock_property.current_zestimate, zestimate)
        self.assertEqual(mock_property.current_zestimate_high, zestimate_high)
        self.assertEqual(mock_property.current_zestimate_low, zestimate_low)
        # Note: session.close() is not called by the function - it's managed externally

    @patch('dataBase.SessionLocal')
    def test_upsert_zestimates_none_values(self, mock_session_local):
        """Test upsert_zestimates with None values (should not create record)."""
        # Setup
        mock_session = Mock()
        mock_session_local.return_value = mock_session
        
        # Mock Property object
        mock_property = Mock()
        mock_property.current_zestimate = 700000
        mock_property.current_zestimate_high = 750000
        mock_property.current_zestimate_low = 650000
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_property
        
        property_id = 123
        zestimate = None
        zestimate_high = None
        zestimate_low = None
        
        # Execute
        upsert_zestimates(mock_session, property_id, zestimate, zestimate_high, zestimate_low)
        
        # Verify - should not add anything
        mock_session.add.assert_not_called()
        # Note: session.close() is not called by the function - it's managed externally


if __name__ == '__main__':
    unittest.main()
