import unittest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, timezone, timedelta
import json
import sys
import os

# Add the project directory to the path so we can import the modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from homes_from_zipcode_helper import (
    fetch_homes_json_from_zipcode,
    fetch_homes_json_via_playwright,
    upsert_initial_info,
    upsert_property,
    upsert_listing,
    get_list_date
)
from dataBase import (
    SessionLocal, Zipcodes, Property, Property_Change, 
    Transaction, Listing, Status_History, Price_History
)


class TestHomesFromZipcodeHelper(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.mock_session = Mock()
        self.mock_zipcode = Mock(spec=Zipcodes)
        self.mock_zipcode.zipcode = "12345"
        self.mock_zipcode.for_sale_request_url = "https://test-for-sale-url.com"
        self.mock_zipcode.sold_request_url = "https://test-sold-url.com"
        
        # Sample home data structure
        self.sample_home = {
            'propertyId': '12345678',
            'streetLine': {'value': '123 Test St'},
            'city': 'Test City',
            'state': 'CA',
            'zip': '12345',
            'latLong': {'value': {'latitude': 37.7749, 'longitude': -122.4194}},
            'lotSize': {'value': 5000},
            'yearBuilt': {'value': 1990},
            'uiPropertyType': 'home',
            'beds': 3,
            'baths': 2,
            'sqFt': {'value': 1500},
            'stories': 2,
            'unitNumber': {'value': None},
            'hoa': {'value': 100},
            'newConstructionCommunityInfo': {'builderName': 'Test Builder'},
            'mlsStatus': 'Active',
            'listingId': 'L123456',
            'dom': {'value': '30'},
            'url': '/CA/Test-City/123-Test-St-12345/home/12345678',
            'isNewConstruction': False,
            'price': {'value': 500000},
            'soldDate': 1640995200000  # Jan 1, 2022
        }
        
    def test_get_list_date_normal_case(self):
        """Test get_list_date with normal DOM values."""
        with patch('homes_from_zipcode_helper.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
            
            test_cases = [
                ({'dom': {'value': '30'}, 'propertyId': '123'}, '2024-12-16'),
                ({'dom': {'value': '0'}, 'propertyId': '456'}, '2025-01-15'),
                ({'dom': {'value': '1'}, 'propertyId': '789'}, '2025-01-14'),
                ({'dom': {'value': '365'}, 'propertyId': '101'}, '2024-01-16'),
                ({'dom': {'value': '-5'}, 'propertyId': '202'}, '2025-01-20'),  # negative numbers are valid (future dates)
                ({'dom': {'value': '-30'}, 'propertyId': '303'}, '2025-02-14'),  # negative numbers are valid (future dates)
            ]
            
            for home_data, expected in test_cases:
                with self.subTest(home_data=home_data):
                    result = get_list_date(home_data)
                    self.assertEqual(result, expected)
    
    @patch('homes_from_zipcode_helper.logger')
    def test_get_list_date_edge_cases(self, mock_logger):
        """Test get_list_date with edge cases."""
        with patch('homes_from_zipcode_helper.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
            
            # Test None DOM
            result = get_list_date({'dom': {'value': None}, 'propertyId': '123'})
            self.assertIsNone(result)
            
            # Test missing DOM
            result = get_list_date({'propertyId': '456'})
            self.assertIsNone(result)
            
            # Test non-numeric DOM
            result = get_list_date({'dom': {'value': 'abc'}, 'propertyId': '789'})
            self.assertIsNone(result)
            
            # Test overflow DOM
            result = get_list_date({'dom': {'value': '999999999'}, 'propertyId': '101'})
            self.assertIsNone(result)
            
            # Verify all warnings were logged
            expected_calls = [
                (("Invalid DOM value: None for home with propertyId 123",),),
                (("Invalid DOM value: None for home with propertyId 456",),),
                (("Invalid DOM value: 'abc' (cannot convert to integer) for home with propertyId 789",),),
                (("Invalid DOM value: '999999999' (causes date overflow) for home with propertyId 101",),),
            ]
            self.assertEqual(mock_logger.warning.call_args_list, expected_calls)
    
    @patch('homes_from_zipcode_helper.fetch_html_via_https')
    @patch('homes_from_zipcode_helper.strip_json_beginning')
    def test_fetch_homes_json_from_zipcode_database_hit_for_sale(self, mock_strip, mock_fetch):
        """Test fetch_homes_json_from_zipcode with database hit for for_sale_homes_fetch."""
        # Setup
        mock_response = {'errorMessage': 'Success', 'payload': {'homes': [self.sample_home]}}
        mock_fetch.return_value = 'mock_html_response'
        import json
        mock_strip.return_value = json.dumps(mock_response)
        
        with patch('homes_from_zipcode_helper.SessionLocal') as mock_session_local:
            mock_session = Mock()
            mock_session_local.return_value = mock_session
            
            # Mock database query
            mock_session.query.return_value.filter.return_value.one_or_none.return_value = self.mock_zipcode
            
            # Execute
            result = fetch_homes_json_from_zipcode("for_sale_homes_fetch", "12345")
            
            # Verify
            self.assertEqual(result, [self.sample_home])
            from unittest.mock import ANY
            mock_fetch.assert_called_once_with(self.mock_zipcode.for_sale_request_url, ANY)
            mock_strip.assert_called_once_with('mock_html_response', '{}&&')
    
    @patch('homes_from_zipcode_helper.fetch_html_via_https')
    @patch('homes_from_zipcode_helper.strip_json_beginning')
    def test_fetch_homes_json_from_zipcode_database_hit_sold(self, mock_strip, mock_fetch):
        """Test fetch_homes_json_from_zipcode with database hit for sold_homes_fetch."""
        # Setup
        mock_response = {'errorMessage': 'Success', 'payload': {'homes': [self.sample_home]}}
        mock_fetch.return_value = 'mock_html_response'
        import json
        mock_strip.return_value = json.dumps(mock_response)
        
        with patch('homes_from_zipcode_helper.SessionLocal') as mock_session_local:
            mock_session = Mock()
            mock_session_local.return_value = mock_session
            
            # Mock database query
            mock_session.query.return_value.filter.return_value.one_or_none.return_value = self.mock_zipcode
            
            # Execute
            result = fetch_homes_json_from_zipcode("sold_homes_fetch", "12345")
            
            # Verify
            self.assertEqual(result, [self.sample_home])
            from unittest.mock import ANY
            mock_fetch.assert_called_once_with(self.mock_zipcode.sold_request_url, ANY)
    
    @patch('homes_from_zipcode_helper.fetch_homes_json_via_playwright')
    def test_fetch_homes_json_from_zipcode_database_miss_for_sale(self, mock_playwright):
        """Test fetch_homes_json_from_zipcode with database miss for for_sale_homes_fetch."""
        # Setup
        mock_response = {'errorMessage': 'Success', 'payload': {'homes': [self.sample_home]}}
        mock_playwright.return_value = (mock_response, 'https://test-url.com')
        
        with patch('homes_from_zipcode_helper.SessionLocal') as mock_session_local:
            mock_session = Mock()
            mock_session_local.return_value = mock_session
            
            # Mock database query - no existing record
            mock_session.query.return_value.filter.return_value.one_or_none.return_value = None
            
            # Fix 2: Create a mock zipcode object instead of None
            mock_existing_zip = Mock(spec=Zipcodes)
            mock_existing_zip.zipcode = "12345"
            mock_session.get.return_value = mock_existing_zip
            
            # Execute
            result = fetch_homes_json_from_zipcode("for_sale_homes_fetch", "12345")
            
            # Verify
            self.assertEqual(result, [self.sample_home])
            mock_playwright.assert_called_once_with("https://www.redfin.com/zipcode/12345")
            
            # Verify database update was attempted
            mock_session.get.assert_called_once_with(Zipcodes, "12345")
            # Verify the URL was set on the mock object
            self.assertEqual(mock_existing_zip.for_sale_request_url, 'https://test-url.com')
    
    @patch('homes_from_zipcode_helper.fetch_homes_json_via_playwright')
    def test_fetch_homes_json_from_zipcode_database_miss_sold(self, mock_playwright):
        """Test fetch_homes_json_from_zipcode with database miss for sold_homes_fetch."""
        # Setup
        mock_response = {'errorMessage': 'Success', 'payload': {'homes': [self.sample_home]}}
        mock_playwright.return_value = (mock_response, 'https://test-url.com')
        
        with patch('homes_from_zipcode_helper.SessionLocal') as mock_session_local:
            mock_session = Mock()
            mock_session_local.return_value = mock_session
            
            # Mock database query - no existing record
            mock_session.query.return_value.filter.return_value.one_or_none.return_value = None
            
            # Fix 2: Create a mock zipcode object instead of None
            mock_existing_zip = Mock(spec=Zipcodes)
            mock_existing_zip.zipcode = "12345"
            mock_session.get.return_value = mock_existing_zip
            
            # Execute
            result = fetch_homes_json_from_zipcode("sold_homes_fetch", "12345")
            
            # Verify
            self.assertEqual(result, [self.sample_home])
            mock_playwright.assert_called_once_with("https://www.redfin.com/zipcode/12345/filter/include=sold-3mo")
            
            # Verify the URL was set on the mock object
            self.assertEqual(mock_existing_zip.sold_request_url, 'https://test-url.com')
    
    def test_fetch_homes_json_from_zipcode_error_response(self):
        """Test fetch_homes_json_from_zipcode with error response."""
        with patch('homes_from_zipcode_helper.fetch_html_via_https') as mock_fetch:
            mock_response = {'errorMessage': 'Failed to fetch data'}
            mock_fetch.return_value = 'mock_html_response'
            
            with patch('homes_from_zipcode_helper.strip_json_beginning') as mock_strip:
                import json
                mock_strip.return_value = json.dumps(mock_response)
                
                with patch('homes_from_zipcode_helper.SessionLocal') as mock_session_local:
                    mock_session = Mock()
                    mock_session_local.return_value = mock_session
                    
                    # Mock database query
                    mock_session.query.return_value.filter.return_value.one_or_none.return_value = self.mock_zipcode
                    
                    # Execute
                    result = fetch_homes_json_from_zipcode("for_sale_homes_fetch", "12345")
                    
                    # Verify
                    self.assertEqual(result, [])
    
    def test_fetch_homes_json_from_zipcode_database_error(self):
        """Test fetch_homes_json_from_zipcode with database error."""
        with patch('homes_from_zipcode_helper.SessionLocal') as mock_session_local:
            mock_session = Mock()
            mock_session_local.return_value = mock_session
            
            # Mock database error
            mock_session.query.side_effect = Exception("Database error")
            
            # Execute and verify exception is raised
            with self.assertRaises(Exception):
                fetch_homes_json_from_zipcode("for_sale_homes_fetch", "12345")
            
            # Verify session was closed
            mock_session.close.assert_called_once()
    
    @patch('homes_from_zipcode_helper.sync_playwright')
    def test_fetch_homes_json_via_playwright_success(self, mock_playwright):
        """Test fetch_homes_json_via_playwright with successful response."""
        # Setup mock Playwright objects
        mock_pw = Mock()
        mock_browser = Mock()
        mock_context = Mock()
        mock_page = Mock()
        mock_response = Mock()
        
        # Configure the mock chain
        mock_playwright.return_value.__enter__.return_value = mock_pw
        mock_pw.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        
        # Fix 3: Set up the context manager properly for expect_response using MagicMock
        mock_response_info = Mock()
        mock_response_info.value = mock_response
        mock_expect_response_context = MagicMock()
        mock_expect_response_context.__enter__.return_value = mock_response_info
        mock_page.expect_response.return_value = mock_expect_response_context
        mock_response.url = "https://test-gis-url.com"
        mock_response.text.return_value = '{}&&{"errorMessage": "Success", "payload": {"homes": []}}'
        
        # Execute
        result, request_url = fetch_homes_json_via_playwright("https://test-url.com")
        
        # Verify
        self.assertEqual(request_url, "https://test-gis-url.com")
        self.assertEqual(result["errorMessage"], "Success")
        mock_browser.close.assert_called_once()
    
    @patch('homes_from_zipcode_helper.sync_playwright')
    def test_fetch_homes_json_via_playwright_timeout(self, mock_playwright):
        """Test fetch_homes_json_via_playwright with timeout."""
        # Setup mock Playwright objects
        mock_pw = Mock()
        mock_browser = Mock()
        mock_context = Mock()
        mock_page = Mock()
        
        # Configure the mock chain
        mock_playwright.return_value.__enter__.return_value = mock_pw
        mock_pw.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        
        # Fix 3: Set up the context manager properly, but make it raise an exception using MagicMock
        mock_expect_response_context = MagicMock()
        mock_expect_response_context.__enter__.side_effect = Exception("Timeout")
        mock_page.expect_response.return_value = mock_expect_response_context
        
        # Execute and verify exception is raised
        with self.assertRaises(Exception):
            fetch_homes_json_via_playwright("https://test-url.com")
        
        # Verify browser was closed even on error
        mock_browser.close.assert_called_once()
    
    def test_upsert_property_new_property(self):
        """Test upsert_property with new property."""
        with patch('homes_from_zipcode_helper.SessionLocal') as mock_session_local:
            mock_session = Mock()
            mock_session_local.return_value = mock_session
            
            # Mock no existing property
            mock_session.query.return_value.filter_by.return_value.first.return_value = None
            
            # Execute
            result = upsert_property(self.sample_home, mock_session)
            
            # Verify
            self.assertTrue(result["isNewProperty"])
            self.assertEqual(result["redfin_property_id"], "12345678")
            self.assertEqual(result["address"], "123 Test St")
            self.assertEqual(result["city"], "Test City")
            self.assertEqual(result["state"], "CA")
            self.assertEqual(result["zipcode"], "12345")
            
            # Verify property was added
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()
    
    def test_upsert_property_existing_property_no_changes(self):
        """Test upsert_property with existing property and no changes."""
        with patch('homes_from_zipcode_helper.SessionLocal') as mock_session_local:
            mock_session = Mock()
            mock_session_local.return_value = mock_session
            
            # Mock existing property with same values
            existing_property = Mock(spec=Property)
            existing_property.property_id = 1
            existing_property.city = "Test City"
            existing_property.state = "CA"
            existing_property.address = "123 Test St"
            existing_property.zipcode = "12345"
            existing_property.redfin_property_id = "12345678"
            existing_property.is_on_market = True
            
            # Mock all attributes to be the same
            for attr_name in ['city', 'state', 'address', 'zipcode', 'redfin_property_id', 'is_on_market']:
                setattr(existing_property, attr_name, getattr(existing_property, attr_name))
            
            mock_session.query.return_value.filter_by.return_value.first.return_value = existing_property
            
            # Execute
            result = upsert_property(self.sample_home, mock_session)
            
            # Verify
            self.assertFalse(result["isNewProperty"])
            self.assertEqual(result["property_id"], 1)
            
            # Verify no Property_Change records were added
            property_change_calls = [call for call in mock_session.add.call_args_list 
                                   if 'Property_Change' in str(call)]
            self.assertEqual(len(property_change_calls), 0)
    
    def test_upsert_property_existing_property_with_changes(self):
        """Test upsert_property with existing property and changes."""
        with patch('homes_from_zipcode_helper.SessionLocal') as mock_session_local:
            mock_session = Mock()
            mock_session_local.return_value = mock_session
            
            # Mock existing property with different values
            existing_property = Mock()
            existing_property.property_id = 1
            existing_property.city = "Old City"  # Different from sample_home's "Test City"
            existing_property.state = "CA"  # Different from sample_home's "CA" (actually same, but let's use different)
            existing_property.address = "123 Test St"
            existing_property.zipcode = "12345"
            existing_property.redfin_property_id = "12345678"
            existing_property.is_on_market = True
            
            # Mock inspect to return column attributes
            mock_inspect = Mock()
            mock_inspect.attrs = [
                Mock(key='city', columns=[Mock(primary_key=False)]),
                Mock(key='state', columns=[Mock(primary_key=False)]),
                Mock(key='address', columns=[Mock(primary_key=False)]),
                Mock(key='zipcode', columns=[Mock(primary_key=False)]),
                Mock(key='redfin_property_id', columns=[Mock(primary_key=False)]),
                Mock(key='property_id', columns=[Mock(primary_key=True)]),  # Skip primary key
            ]
            
            # Mock the Property constructor to return a mock with the correct attributes
            mock_new_property = Mock()
            mock_new_property.city = "Test City"  # From sample_home
            mock_new_property.state = "CA"  # From sample_home
            mock_new_property.address = "123 Test St"  # From sample_home
            mock_new_property.zipcode = "12345"  # From sample_home
            mock_new_property.redfin_property_id = "12345678"  # From sample_home
            mock_new_property.is_on_market = True  # From sample_home logic
            
            with patch('homes_from_zipcode_helper.inspect', return_value=mock_inspect):
                with patch('homes_from_zipcode_helper.Property') as mock_property_class:
                    mock_property_class.return_value = mock_new_property
                    
                    mock_session.query.return_value.filter_by.return_value.first.return_value = existing_property
                    
                    # Execute
                    result = upsert_property(self.sample_home, mock_session)
                    
                    # Verify
                    self.assertFalse(result["isNewProperty"])
                    self.assertEqual(result["property_id"], 1)
                    
                    # Verify Property_Change record was added for city change
                    property_change_calls = [call for call in mock_session.add.call_args_list 
                                           if hasattr(call[0][0], '__class__') and 'property_change' in str(call[0][0].__class__).lower()]
                    self.assertGreater(len(property_change_calls), 0)
    
    def test_upsert_property_sold_transaction(self):
        """Test upsert_property when property is sold."""
        with patch('homes_from_zipcode_helper.SessionLocal') as mock_session_local:
            mock_session = Mock()
            mock_session_local.return_value = mock_session
            
            # Mock existing property that was on market
            existing_property = Mock()
            existing_property.property_id = 1
            existing_property.is_on_market = True  # Was on market before
            existing_property.city = "Test City"
            existing_property.state = "CA"
            existing_property.address = "123 Test St"
            existing_property.zipcode = "12345"
            existing_property.redfin_property_id = "12345678"
            
            # Create sold home data
            sold_home = self.sample_home.copy()
            sold_home['mlsStatus'] = 'Sold'  # Now sold
            sold_home['soldDate'] = 1640995200000  # Jan 1, 2022
            
            mock_session.query.return_value.filter_by.return_value.first.return_value = existing_property
            
            # Mock inspect
            mock_inspect = Mock()
            mock_inspect.attrs = [
                Mock(key='is_on_market', columns=[Mock(primary_key=False)]),
                Mock(key='property_id', columns=[Mock(primary_key=True)]),
            ]
            
            # Mock the Property constructor to return a mock with the correct attributes
            mock_new_property = Mock()
            mock_new_property.is_on_market = False  # Sold properties are not on market
            mock_new_property.property_id = 1
            mock_new_property.redfin_property_id = "12345678"
            
            with patch('homes_from_zipcode_helper.inspect', return_value=mock_inspect):
                with patch('homes_from_zipcode_helper.Property') as mock_property_class, \
                     patch('homes_from_zipcode_helper.Transaction') as mock_transaction_class:
                    mock_property_class.return_value = mock_new_property
                    mock_transaction = Mock()
                    mock_transaction_class.return_value = mock_transaction
                    
                    # Execute
                    result = upsert_property(sold_home, mock_session)
                    
                    # Verify Transaction record was added
                    mock_session.add.assert_any_call(mock_transaction)
    
    def test_upsert_listing_new_listing(self):
        """Test upsert_listing with new listing."""
        with patch('homes_from_zipcode_helper.get_list_date') as mock_get_list_date:
            mock_get_list_date.return_value = "2024-12-16"
            
            with patch('homes_from_zipcode_helper.SessionLocal') as mock_session_local:
                mock_session = Mock()
                mock_session_local.return_value = mock_session
                
                # Mock no existing listing
                mock_session.query.return_value.filter_by.return_value.first.return_value = None
                
                # Mock the new listing object that will be created
                mock_new_listing = Mock()
                mock_new_listing.listing_id = 123  # Set the expected listing_id
                
                # Mock the Listing constructor to return our mock object
                with patch('homes_from_zipcode_helper.Listing') as mock_listing_class:
                    mock_listing_class.return_value = mock_new_listing
                    
                    # Execute
                    result = upsert_listing(self.sample_home, 1, mock_session)
                    
                    # Verify
                    self.assertEqual(result, 123)  # Should return the listing_id
                    mock_session.add.assert_called_once_with(mock_new_listing)
                    mock_session.flush.assert_called_once()
    
    def test_upsert_listing_existing_listing_status_change(self):
        """Test upsert_listing with existing listing and status change."""
        with patch('homes_from_zipcode_helper.get_list_date') as mock_get_list_date:
            mock_get_list_date.return_value = "2024-12-16"
            
            with patch('homes_from_zipcode_helper.SessionLocal') as mock_session_local:
                mock_session = Mock()
                mock_session_local.return_value = mock_session
                
                # Mock existing listing with different status
                existing_listing = Mock()
                existing_listing.listing_id = 1
                existing_listing.current_status = "Pending"  # Different from sample_home's "Active"
                existing_listing.current_price = 500000  # Same as sample_home to avoid price change
                
                mock_session.query.return_value.filter_by.return_value.first.return_value = existing_listing
                
                # Mock the Listing constructor to return a mock with the correct status
                mock_new_listing = Mock()
                mock_new_listing.current_status = "Active"  # From sample_home
                mock_new_listing.current_price = 500000  # From sample_home
                
                with patch('homes_from_zipcode_helper.Listing') as mock_listing_class:
                    mock_listing_class.return_value = mock_new_listing
                    
                    # Execute
                    result = upsert_listing(self.sample_home, 1, mock_session)
                    
                    # Verify
                    self.assertEqual(result, 1)
                    
                    # Verify Status_History record was added
                    status_history_calls = [call for call in mock_session.add.call_args_list 
                                          if hasattr(call[0][0], '__class__') and 'status_history' in str(call[0][0].__class__).lower()]
                    self.assertGreater(len(status_history_calls), 0)
    
    def test_upsert_listing_existing_listing_price_change(self):
        """Test upsert_listing with existing listing and price change."""
        with patch('homes_from_zipcode_helper.get_list_date') as mock_get_list_date:
            mock_get_list_date.return_value = "2024-12-16"
            
            with patch('homes_from_zipcode_helper.SessionLocal') as mock_session_local:
                mock_session = Mock()
                mock_session_local.return_value = mock_session
                
                # Mock existing listing with different price
                existing_listing = Mock()
                existing_listing.listing_id = 1
                existing_listing.current_status = "Active"  # Same as sample_home to avoid status change
                existing_listing.current_price = 450000  # Different from sample_home's 500000
                
                mock_session.query.return_value.filter_by.return_value.first.return_value = existing_listing
                
                # Mock the Listing constructor to return a mock with the correct price
                mock_new_listing = Mock()
                mock_new_listing.current_status = "Active"  # From sample_home
                mock_new_listing.current_price = 500000  # From sample_home
                
                with patch('homes_from_zipcode_helper.Listing') as mock_listing_class:
                    mock_listing_class.return_value = mock_new_listing
                    
                    # Execute
                    result = upsert_listing(self.sample_home, 1, mock_session)
                    
                    # Verify
                    self.assertEqual(result, 1)
                    
                    # Verify Price_History record was added
                    price_history_calls = [call for call in mock_session.add.call_args_list 
                                         if hasattr(call[0][0], '__class__') and 'price_history' in str(call[0][0].__class__).lower()]
                    self.assertGreater(len(price_history_calls), 0)
    
    def test_upsert_initial_info_success(self):
        """Test upsert_initial_info with successful operations."""
        with patch('homes_from_zipcode_helper.upsert_property') as mock_upsert_property:
            with patch('homes_from_zipcode_helper.upsert_listing') as mock_upsert_listing:
                mock_upsert_property.return_value = {"property_id": 1, "isNewProperty": True}
                mock_upsert_listing.return_value = 100
                
                # Execute
                result = upsert_initial_info(self.mock_session, self.sample_home)
                
                # Verify
                self.assertEqual(result["property_id"], 1)
                self.assertEqual(result["listing_id"], 100)
                self.assertTrue(result["isNewProperty"])
                
                mock_upsert_property.assert_called_once_with(self.sample_home, self.mock_session)
                mock_upsert_listing.assert_called_once_with(self.sample_home, 1, self.mock_session)
    
    def test_upsert_initial_info_exception(self):
        """Test upsert_initial_info with exception."""
        with patch('homes_from_zipcode_helper.upsert_property') as mock_upsert_property:
            mock_upsert_property.side_effect = Exception("Test error")
            
            # Execute and verify exception is raised
            with self.assertRaises(Exception):
                upsert_initial_info(self.mock_session, self.sample_home)
            
            # Verify rollback was called
            self.mock_session.rollback.assert_called_once()
    
    def test_upsert_property_database_error(self):
        """Test upsert_property with database error."""
        with patch('homes_from_zipcode_helper.SessionLocal') as mock_session_local:
            mock_session = Mock()
            mock_session_local.return_value = mock_session
            
            # Mock database error
            mock_session.query.side_effect = Exception("Database error")
            
            # Execute and verify exception is raised
            with self.assertRaises(Exception):
                upsert_property(self.sample_home, mock_session)
            
            # Verify session was rolled back and closed (both should happen due to try-except-finally)
            mock_session.rollback.assert_called_once()
            mock_session.close.assert_called_once()
    
    def test_upsert_listing_database_error(self):
        """Test upsert_listing with database error."""
        with patch('homes_from_zipcode_helper.get_list_date') as mock_get_list_date:
            mock_get_list_date.return_value = "2024-12-16"
            
            with patch('homes_from_zipcode_helper.SessionLocal') as mock_session_local:
                mock_session = Mock()
                mock_session_local.return_value = mock_session
                
                # Mock database error
                mock_session.query.side_effect = Exception("Database error")
                
                # Execute and verify exception is raised
                with self.assertRaises(Exception):
                    upsert_listing(self.sample_home, 1, mock_session)
                
                # Verify session was rolled back
                mock_session.rollback.assert_called_once()


if __name__ == '__main__':
    unittest.main()