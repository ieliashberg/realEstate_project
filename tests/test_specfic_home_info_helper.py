import unittest
from unittest.mock import Mock, patch, ANY
import sys
import os

# Add the project directory to the path so we can import the modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from specfic_home_info_helper import (
    create_url,
    get_specific_property_info,
    get_property_json,
    clean_price,
    upsert_more_info
)


class TestSpecficHomeInfoHelper(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.sample_payload = {
            "address": "123 Main St",
            "city": "San Francisco",
            "state": "CA",
            "zipcode": "94102",
            "redfin_property_id": "12345678"
        }
        
        self.sample_html = '''
        <html>
        <head><title>Test Property</title></head>
        <body>
        <script type="text/javascript">
        window.__INITIAL_STATE__ = {
            "cat1": {
                "searchResults": {
                    "mapResults": [{
                        "zpid": "123456",
                        "propertyType": "SINGLE_FAMILY",
                        "price": 750000,
                        "beds": 3,
                        "baths": 2,
                        "sqft": 1500
                    }]
                }
            }
        };
        </script>
        </body>
        </html>
        '''

    def test_create_url_basic(self):
        """Test URL creation with basic payload."""
        result = create_url(self.sample_payload)
        expected = "https://www.redfin.com/CA/san-francisco/123-main-st-94102/home/12345678"
        self.assertEqual(result, expected)

    def test_get_specific_property_info_with_original_url(self):
        """Test that function uses original Redfin URL when available."""
        payload_with_url = {
            "address": "123 Main St",
            "city": "San Francisco", 
            "state": "CA",
            "zipcode": "94102",
            "redfin_property_id": "12345678",
            "url": "/CA/San-Francisco/123-Main-St-94102/home/12345678"  # Original Redfin URL
        }
        
        with patch('specfic_home_info_helper.fetch_html_via_https') as mock_fetch:
            mock_fetch.return_value = self.sample_html
            
            result = get_specific_property_info(payload_with_url)
            
            # Verify it used the original URL (with base URL prepended)
            expected_url = "https://www.redfin.com/CA/San-Francisco/123-Main-St-94102/home/12345678"
            mock_fetch.assert_called_once_with(expected_url, ANY)
            self.assertIsInstance(result, dict)

    def test_create_url_with_spaces(self):
        """Test URL creation with spaces in address."""
        payload = self.sample_payload.copy()
        payload["address"] = "123 Main Street Apt 4B"
        result = create_url(payload)
        expected = "https://www.redfin.com/CA/san-francisco/123-main-street-apt-4b-94102/home/12345678"
        self.assertEqual(result, expected)

    def test_create_url_mixed_case(self):
        """Test URL creation with mixed case input."""
        payload = {
            "address": "123 MAIN St",
            "city": "San Francisco",
            "state": "CA",
            "zipcode": "94102",
            "redfin_property_id": "12345678"
        }
        result = create_url(payload)
        expected = "https://www.redfin.com/CA/san-francisco/123-main-st-94102/home/12345678"
        self.assertEqual(result, expected)

    def test_clean_price_normal_format(self):
        """Test clean_price with normal price format."""
        test_cases = [
            ("$500,000", 500000),
            ("$1,250,000", 1250000),
            ("500000", 500000),
            ("1,250,000", 1250000),
        ]
        
        for input_price, expected in test_cases:
            with self.subTest(input_price=input_price):
                result = clean_price(input_price)
                self.assertEqual(result, expected)

    def test_clean_price_with_parentheses(self):
        """Test clean_price with parentheses (should drop everything after '(')."""
        test_cases = [
            ("$500,000 (estimated)", 500000),
            ("$1,250,000 (recently sold)", 1250000),
            ("$750,000 (pending)", 750000),
        ]
        
        for input_price, expected in test_cases:
            with self.subTest(input_price=input_price):
                result = clean_price(input_price)
                self.assertEqual(result, expected)

    def test_clean_price_invalid_input(self):
        """Test clean_price with invalid input."""
        invalid_inputs = [None, "", "invalid", "N/A", "-"]
        
        for invalid_input in invalid_inputs:
            with self.subTest(invalid_input=invalid_input):
                result = clean_price(invalid_input)
                self.assertIsNone(result)

    def test_get_property_json_success(self):
        """Test successful property JSON extraction."""
        result = get_property_json(self.sample_html)
        
        self.assertIsInstance(result, dict)
        self.assertIn("cat1", result)
        self.assertIn("searchResults", result["cat1"])
        self.assertIn("mapResults", result["cat1"]["searchResults"])

    def test_get_property_json_no_script_tags(self):
        """Test property JSON extraction when no script tags exist."""
        html = "<html><body><p>No scripts here</p></body></html>"
        
        with self.assertRaises(ValueError) as context:
            get_property_json(html)
        
        self.assertIn("No script tags with type='text/javascript'", str(context.exception))

    def test_get_property_json_no_initial_state(self):
        """Test property JSON extraction when no INITIAL_STATE is found."""
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
            get_property_json(html)
        
        self.assertIn("Could not find any <script> with window.__INITIAL_STATE__", str(context.exception))

    @patch('specfic_home_info_helper.fetch_html_via_https')
    def test_get_specific_property_info_success(self, mock_fetch_html):
        """Test successful specific property info retrieval."""
        # Setup
        mock_fetch_html.return_value = self.sample_html
        
        # Execute
        result = get_specific_property_info(self.sample_payload)
        
        # Verify
        self.assertIsInstance(result, dict)
        mock_fetch_html.assert_called_once()

    @patch('specfic_home_info_helper.fetch_html_via_https')
    def test_get_specific_property_info_no_html(self, mock_fetch_html):
        """Test specific property info when no HTML is returned."""
        # Setup
        mock_fetch_html.return_value = None
        
        # Execute
        result = get_specific_property_info(self.sample_payload)
        
        # Verify
        self.assertIsNone(result)

    @patch('specfic_home_info_helper.fetch_html_via_https')
    def test_get_specific_property_info_exception(self, mock_fetch_html):
        """Test specific property info when an exception occurs."""
        # Setup
        mock_fetch_html.side_effect = Exception("Network error")
        
        # Execute
        result = get_specific_property_info(self.sample_payload)
        
        # Verify
        self.assertIsNone(result)

    @patch('dataBase.SessionLocal')
    def test_upsert_more_info_success(self, mock_session_local):
        """Test successful upsert of more property info."""
        # Setup
        mock_session = Mock()
        mock_session_local.return_value = mock_session
        
        mock_property = Mock()
        mock_session.query.return_value.filter_by.return_value.one.return_value = mock_property
        
        extra_info = {
            "schools": [{"name": "Test School", "rating": 8}],
            "price_history": [{"date": "2023-01-01", "price": 500000}],
            "covered_spaces": ["garage", "patio"],
            "tax_annual_amount": 5000,
            "agents_name": "John Doe",
            "agents_broker": "ABC Realty"
        }
        
        property_id = 123
        listing_id = 456
        is_new_property = False
        
        # Execute
        upsert_more_info(mock_session, extra_info, property_id, listing_id, is_new_property)
        
        # Verify
        self.assertGreater(mock_session.query.call_count, 0)  # Function makes multiple queries
        # Note: session.close() is not called by the function - it's managed externally

    @patch('dataBase.SessionLocal')
    def test_upsert_more_info_none_extra_info(self, mock_session_local):
        """Test upsert_more_info with None extra_info."""
        # Setup
        mock_session = Mock()
        mock_session_local.return_value = mock_session
        
        # Execute
        upsert_more_info(mock_session, None, 123, 456, False)
        
        # Verify - should not do anything
        mock_session.query.assert_not_called()
        mock_session.commit.assert_not_called()
        mock_session.close.assert_not_called()  # Function returns early, doesn't close session

    @patch('dataBase.SessionLocal')
    def test_upsert_more_info_empty_extra_info(self, mock_session_local):
        """Test upsert_more_info with empty extra_info."""
        # Setup
        mock_session = Mock()
        mock_session_local.return_value = mock_session
        
        mock_property = Mock()
        mock_session.query.return_value.filter_by.return_value.one.return_value = mock_property
        
        extra_info = {}
        
        # Execute
        upsert_more_info(mock_session, extra_info, 123, 456, False)
        
        # Verify
        self.assertGreater(mock_session.query.call_count, 0)  # Function makes multiple queries
        # Note: session.close() is not called by the function - it's managed externally


if __name__ == '__main__':
    unittest.main()
