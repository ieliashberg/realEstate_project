"""
Comprehensive tests for homes_from_zipcode_helper.py including error handling and edge cases.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from src.scrapers.redfin.parsers import (
    fetch_homes_json_from_zipcode,
    upsert_property,
    fetch_bounds_for_zip,
    strip_json_beginning
)


class TestFetchHomesJsonFromZipcode:
    """Test the main homes fetching functionality."""

    def test_fetch_homes_json_from_zipcode_valid_zipcode(self):
        """Test fetching homes with valid zipcode."""
        with patch('homes_from_zipcode_helper.fetch_html_via_https') as mock_fetch:
            mock_fetch.return_value = '''
            <html>
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
                            "sqft": 1500,
                            "address": "123 Main St",
                            "city": "Gilbert",
                            "state": "AZ",
                            "zipcode": "85297",
                            "url": "/AZ/Gilbert/123-Main-St-85297/home/123456"
                        }]
                    }
                }
            };
            </script>
            </html>
            '''
            
            result = fetch_homes_json_from_zipcode("85297", "for_sale")
            
            assert len(result) == 1
            assert result[0]["address"] == "123 Main St"
            assert result[0]["city"] == "Gilbert"
            assert result[0]["state"] == "AZ"
            assert result[0]["zipcode"] == "85297"

    def test_fetch_homes_json_from_zipcode_invalid_zipcode(self):
        """Test fetching homes with invalid zipcode."""
        with patch('homes_from_zipcode_helper.fetch_html_via_https') as mock_fetch:
            mock_fetch.return_value = None
            
            result = fetch_homes_json_from_zipcode("invalid_zipcode", "for_sale")
            
            assert result == []

    def test_fetch_homes_json_from_zipcode_none_zipcode(self):
        """Test fetching homes with None zipcode."""
        with pytest.raises((TypeError, AttributeError)):
            fetch_homes_json_from_zipcode(None, "for_sale")

    def test_fetch_homes_json_from_zipcode_empty_zipcode(self):
        """Test fetching homes with empty zipcode."""
        result = fetch_homes_json_from_zipcode("", "for_sale")
        assert result == []

    def test_fetch_homes_json_from_zipcode_invalid_type(self):
        """Test fetching homes with invalid type."""
        with patch('homes_from_zipcode_helper.fetch_html_via_https') as mock_fetch:
            mock_fetch.return_value = '''
            <html>
            <script type="text/javascript">
            window.__INITIAL_STATE__ = {
                "cat1": {
                    "searchResults": {
                        "mapResults": []
                    }
                }
            };
            </script>
            </html>
            '''
            
            result = fetch_homes_json_from_zipcode("85297", "invalid_type")
            
            assert result == []

    def test_fetch_homes_json_from_zipcode_with_malformed_html(self):
        """Test fetching homes with malformed HTML."""
        with patch('homes_from_zipcode_helper.fetch_html_via_https') as mock_fetch:
            mock_fetch.return_value = '''
            <html>
            <script type="text/javascript">
            window.__INITIAL_STATE__ = { invalid json };
            </script>
            </html>
            '''
            
            result = fetch_homes_json_from_zipcode("85297", "for_sale")
            
            assert result == []

    def test_fetch_homes_json_from_zipcode_with_empty_html(self):
        """Test fetching homes with empty HTML."""
        with patch('homes_from_zipcode_helper.fetch_html_via_https') as mock_fetch:
            mock_fetch.return_value = ""
            
            result = fetch_homes_json_from_zipcode("85297", "for_sale")
            
            assert result == []

    def test_fetch_homes_json_from_zipcode_with_no_script_tags(self):
        """Test fetching homes with HTML containing no script tags."""
        with patch('homes_from_zipcode_helper.fetch_html_via_https') as mock_fetch:
            mock_fetch.return_value = "<html><body>No scripts</body></html>"
            
            result = fetch_homes_json_from_zipcode("85297", "for_sale")
            
            assert result == []

    def test_fetch_homes_json_from_zipcode_with_no_initial_state(self):
        """Test fetching homes with HTML containing no INITIAL_STATE."""
        with patch('homes_from_zipcode_helper.fetch_html_via_https') as mock_fetch:
            mock_fetch.return_value = '''
            <html>
            <script type="text/javascript">
            var otherData = { "not": "initial_state" };
            </script>
            </html>
            '''
            
            result = fetch_homes_json_from_zipcode("85297", "for_sale")
            
            assert result == []

    def test_fetch_homes_json_from_zipcode_with_empty_results(self):
        """Test fetching homes when no results are returned."""
        with patch('homes_from_zipcode_helper.fetch_html_via_https') as mock_fetch:
            mock_fetch.return_value = '''
            <html>
            <script type="text/javascript">
            window.__INITIAL_STATE__ = {
                "cat1": {
                    "searchResults": {
                        "mapResults": []
                    }
                }
            };
            </script>
            </html>
            '''
            
            result = fetch_homes_json_from_zipcode("85297", "for_sale")
            
            assert result == []

    def test_fetch_homes_json_from_zipcode_with_missing_fields(self):
        """Test fetching homes with missing required fields."""
        with patch('homes_from_zipcode_helper.fetch_html_via_https') as mock_fetch:
            mock_fetch.return_value = '''
            <html>
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
                            // Missing address, city, state, zipcode, url
                        }]
                    }
                }
            };
            </script>
            </html>
            '''
            
            result = fetch_homes_json_from_zipcode("85297", "for_sale")
            
            assert result == []

    def test_fetch_homes_json_from_zipcode_with_unicode_characters(self):
        """Test fetching homes with unicode characters in data."""
        with patch('homes_from_zipcode_helper.fetch_html_via_https') as mock_fetch:
            mock_fetch.return_value = '''
            <html>
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
                            "sqft": 1500,
                            "address": "123 Main St 🏠",
                            "city": "Gilbert",
                            "state": "AZ",
                            "zipcode": "85297",
                            "url": "/AZ/Gilbert/123-Main-St-85297/home/123456"
                        }]
                    }
                }
            };
            </script>
            </html>
            '''
            
            result = fetch_homes_json_from_zipcode("85297", "for_sale")
            
            assert len(result) == 1
            assert result[0]["address"] == "123 Main St 🏠"

    def test_fetch_homes_json_from_zipcode_with_special_characters_in_address(self):
        """Test fetching homes with special characters in address."""
        with patch('homes_from_zipcode_helper.fetch_html_via_https') as mock_fetch:
            mock_fetch.return_value = '''
            <html>
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
                            "sqft": 1500,
                            "address": "123 Main St #101",
                            "city": "Gilbert",
                            "state": "AZ",
                            "zipcode": "85297",
                            "url": "/AZ/Gilbert/123-Main-St-101-85297/home/123456"
                        }]
                    }
                }
            };
            </script>
            </html>
            '''
            
            result = fetch_homes_json_from_zipcode("85297", "for_sale")
            
            assert len(result) == 1
            assert result[0]["address"] == "123 Main St #101"


class TestUpsertProperty:
    """Test property upsert functionality."""

    def test_upsert_property_new_property(self, mock_session):
        """Test creating a new property."""
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        
        home_data = {
            "address": "123 Main St",
            "city": "Gilbert",
            "state": "AZ",
            "zipcode": "85297",
            "redfin_property_id": "12345678",
            "url": "/AZ/Gilbert/123-Main-St-85297/home/12345678"
        }
        
        result = upsert_property(home_data, mock_session)
        
        mock_session.add.assert_called()
        assert result is not None

    def test_upsert_property_existing_property(self, mock_session):
        """Test updating an existing property."""
        mock_existing_property = Mock()
        mock_existing_property.property_id = 12345
        mock_existing_property.address = "123 Main St"
        mock_existing_property.city = "Gilbert"
        mock_existing_property.state = "AZ"
        mock_existing_property.zipcode = "85297"
        mock_existing_property.redfin_property_id = "12345678"
        
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_existing_property
        
        home_data = {
            "address": "123 Main St",
            "city": "Gilbert",
            "state": "AZ",
            "zipcode": "85297",
            "redfin_property_id": "12345678",
            "url": "/AZ/Gilbert/123-Main-St-85297/home/12345678"
        }
        
        result = upsert_property(home_data, mock_session)
        
        assert result == 12345

    def test_upsert_property_with_missing_required_fields(self, mock_session):
        """Test upserting property with missing required fields."""
        home_data = {
            "address": "123 Main St"
            # Missing city, state, zipcode, redfin_property_id
        }
        
        with pytest.raises(KeyError):
            upsert_property(home_data, mock_session)

    def test_upsert_property_with_none_values(self, mock_session):
        """Test upserting property with None values."""
        home_data = {
            "address": None,
            "city": "Gilbert",
            "state": "AZ",
            "zipcode": "85297",
            "redfin_property_id": "12345678",
            "url": "/AZ/Gilbert/123-Main-St-85297/home/12345678"
        }
        
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        
        result = upsert_property(home_data, mock_session)
        
        mock_session.add.assert_called()

    def test_upsert_property_with_empty_strings(self, mock_session):
        """Test upserting property with empty strings."""
        home_data = {
            "address": "",
            "city": "Gilbert",
            "state": "AZ",
            "zipcode": "85297",
            "redfin_property_id": "12345678",
            "url": "/AZ/Gilbert/123-Main-St-85297/home/12345678"
        }
        
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        
        result = upsert_property(home_data, mock_session)
        
        mock_session.add.assert_called()

    def test_upsert_property_with_database_error(self, mock_session):
        """Test handling of database errors during upsert."""
        home_data = {
            "address": "123 Main St",
            "city": "Gilbert",
            "state": "AZ",
            "zipcode": "85297",
            "redfin_property_id": "12345678",
            "url": "/AZ/Gilbert/123-Main-St-85297/home/12345678"
        }
        
        mock_session.add.side_effect = Exception("Database error")
        
        with pytest.raises(Exception, match="Database error"):
            upsert_property(home_data, mock_session)


class TestFetchBoundsForZip:
    """Test bounds fetching functionality."""

    def test_fetch_bounds_for_zip_valid_zipcode(self, mock_session):
        """Test fetching bounds for valid zipcode."""
        mock_bounds = Mock()
        mock_bounds.north = 33.5
        mock_bounds.south = 33.4
        mock_bounds.east = -111.7
        mock_bounds.west = -111.8
        
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_bounds
        
        result = fetch_bounds_for_zip("85297", mock_session)
        
        assert result == mock_bounds

    def test_fetch_bounds_for_zip_invalid_zipcode(self, mock_session):
        """Test fetching bounds for invalid zipcode."""
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        
        result = fetch_bounds_for_zip("invalid_zipcode", mock_session)
        
        assert result is None

    def test_fetch_bounds_for_zip_none_zipcode(self, mock_session):
        """Test fetching bounds for None zipcode."""
        with pytest.raises((TypeError, AttributeError)):
            fetch_bounds_for_zip(None, mock_session)

    def test_fetch_bounds_for_zip_with_database_error(self, mock_session):
        """Test handling of database errors during bounds fetch."""
        mock_session.query.side_effect = Exception("Database error")
        
        with pytest.raises(Exception, match="Database error"):
            fetch_bounds_for_zip("85297", mock_session)


class TestStripJsonBeginning:
    """Test JSON prefix stripping functionality."""

    def test_strip_json_beginning_valid_prefix(self):
        """Test stripping valid prefix from JSON."""
        text = '{}&&{"key": "value"}'
        result = strip_json_beginning(text, '{}&&')
        assert result == '{"key": "value"}'

    def test_strip_json_beginning_without_prefix(self):
        """Test stripping when prefix is not present."""
        text = '{"key": "value"}'
        result = strip_json_beginning(text, '{}&&')
        assert result == '{"key": "value"}'

    def test_strip_json_beginning_with_empty_text(self):
        """Test stripping with empty text."""
        result = strip_json_beginning("", '{}&&')
        assert result == ""

    def test_strip_json_beginning_with_none_text(self):
        """Test stripping with None text."""
        with pytest.raises((TypeError, AttributeError)):
            strip_json_beginning(None, '{}&&')

    def test_strip_json_beginning_with_none_prefix(self):
        """Test stripping with None prefix."""
        with pytest.raises((TypeError, AttributeError)):
            strip_json_beginning('{"key": "value"}', None)

    def test_strip_json_beginning_with_empty_prefix(self):
        """Test stripping with empty prefix."""
        text = '{"key": "value"}'
        result = strip_json_beginning(text, '')
        assert result == '{"key": "value"}'

    def test_strip_json_beginning_with_multiple_prefixes(self):
        """Test stripping with multiple occurrences of prefix."""
        text = '{}&&{}&&{"key": "value"}'
        result = strip_json_beginning(text, '{}&&')
        assert result == '{}&&{"key": "value"}'

    def test_strip_json_beginning_with_unicode_prefix(self):
        """Test stripping with unicode prefix."""
        text = '🏠&&{"key": "value"}'
        result = strip_json_beginning(text, '🏠&&')
        assert result == '{"key": "value"}'


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_fetch_homes_json_from_zipcode_with_very_large_html(self):
        """Test handling of very large HTML."""
        large_html = "<html><script>window.__INITIAL_STATE__ = {};</script>" + "x" * 1000000 + "</html>"
        
        with patch('homes_from_zipcode_helper.fetch_html_via_https') as mock_fetch:
            mock_fetch.return_value = large_html
            
            result = fetch_homes_json_from_zipcode("85297", "for_sale")
            
            # Should handle large HTML gracefully
            assert result == []

    def test_fetch_homes_json_from_zipcode_with_very_large_results(self):
        """Test handling of very large result sets."""
        large_results = []
        for i in range(10000):
            large_results.append({
                "zpid": str(i),
                "propertyType": "SINGLE_FAMILY",
                "price": 750000,
                "beds": 3,
                "baths": 2,
                "sqft": 1500,
                "address": f"{i} Main St",
                "city": "Gilbert",
                "state": "AZ",
                "zipcode": "85297",
                "url": f"/AZ/Gilbert/{i}-Main-St-85297/home/{i}"
            })
        
        with patch('homes_from_zipcode_helper.fetch_html_via_https') as mock_fetch:
            mock_fetch.return_value = f'''
            <html>
            <script type="text/javascript">
            window.__INITIAL_STATE__ = {{
                "cat1": {{
                    "searchResults": {{
                        "mapResults": {json.dumps(large_results)}
                    }}
                }}
            }};
            </script>
            </html>
            '''
            
            result = fetch_homes_json_from_zipcode("85297", "for_sale")
            
            assert len(result) == 10000

    def test_upsert_property_with_very_long_address(self, mock_session):
        """Test upserting property with very long address."""
        long_address = "A" * 10000
        
        home_data = {
            "address": long_address,
            "city": "Gilbert",
            "state": "AZ",
            "zipcode": "85297",
            "redfin_property_id": "12345678",
            "url": "/AZ/Gilbert/123-Main-St-85297/home/12345678"
        }
        
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        
        result = upsert_property(home_data, mock_session)
        
        mock_session.add.assert_called()

    def test_upsert_property_with_special_characters_in_all_fields(self, mock_session):
        """Test upserting property with special characters in all fields."""
        home_data = {
            "address": "123 Main St #101 🏠",
            "city": "Gilbert-City",
            "state": "AZ",
            "zipcode": "85297",
            "redfin_property_id": "12345678",
            "url": "/AZ/Gilbert-City/123-Main-St-101-85297/home/12345678"
        }
        
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        
        result = upsert_property(home_data, mock_session)
        
        mock_session.add.assert_called()

    def test_fetch_homes_json_from_zipcode_with_mixed_data_types(self):
        """Test fetching homes with mixed data types in results."""
        with patch('homes_from_zipcode_helper.fetch_html_via_https') as mock_fetch:
            mock_fetch.return_value = '''
            <html>
            <script type="text/javascript">
            window.__INITIAL_STATE__ = {
                "cat1": {
                    "searchResults": {
                        "mapResults": [{
                            "zpid": "123456",
                            "propertyType": "SINGLE_FAMILY",
                            "price": "750000",
                            "beds": "3",
                            "baths": "2.5",
                            "sqft": "1500",
                            "address": "123 Main St",
                            "city": "Gilbert",
                            "state": "AZ",
                            "zipcode": "85297",
                            "url": "/AZ/Gilbert/123-Main-St-85297/home/123456"
                        }]
                    }
                }
            };
            </script>
            </html>
            '''
            
            result = fetch_homes_json_from_zipcode("85297", "for_sale")
            
            assert len(result) == 1
            assert result[0]["price"] == "750000"  # Should preserve original data type
            assert result[0]["beds"] == "3"
            assert result[0]["baths"] == "2.5"

    def test_fetch_homes_json_from_zipcode_with_null_values(self):
        """Test fetching homes with null values in results."""
        with patch('homes_from_zipcode_helper.fetch_html_via_https') as mock_fetch:
            mock_fetch.return_value = '''
            <html>
            <script type="text/javascript">
            window.__INITIAL_STATE__ = {
                "cat1": {
                    "searchResults": {
                        "mapResults": [{
                            "zpid": "123456",
                            "propertyType": "SINGLE_FAMILY",
                            "price": null,
                            "beds": null,
                            "baths": null,
                            "sqft": null,
                            "address": "123 Main St",
                            "city": "Gilbert",
                            "state": "AZ",
                            "zipcode": "85297",
                            "url": "/AZ/Gilbert/123-Main-St-85297/home/123456"
                        }]
                    }
                }
            };
            </script>
            </html>
            '''
            
            result = fetch_homes_json_from_zipcode("85297", "for_sale")
            
            assert len(result) == 1
            assert result[0]["price"] is None
            assert result[0]["beds"] is None
            assert result[0]["baths"] is None
            assert result[0]["sqft"] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
