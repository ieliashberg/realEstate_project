"""
Comprehensive tests for specfic_home_info_helper.py including error handling and edge cases.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from specfic_home_info_helper import (
    get_specific_property_info,
    get_property_json,
    _extract_below_the_fold_data,
    create_url,
    clean_price,
    upsert_more_info,
    upsert_school,
    upsert_property_school,
    bootstrap_price_histories,
    bootstrap_sold_histories,
    get_agent_info,
    get_schools,
    get_price_history,
    get_covered_spaces,
    get_tax_annual
)


class TestGetSpecificPropertyInfo:
    """Test the main property info fetching functionality."""

    def test_get_specific_property_info_with_original_url(self, sample_property_payload, sample_redfin_html):
        """Test using original Redfin URL from payload."""
        with patch('specfic_home_info_helper.fetch_html_via_https') as mock_fetch:
            mock_fetch.return_value = sample_redfin_html
            
            result = get_specific_property_info(sample_property_payload)
            
            expected_url = "https://www.redfin.com/AZ/Gilbert/123-Main-St-85297/home/12345678"
            mock_fetch.assert_called_once_with(expected_url, Mock())
            assert result is not None

    def test_get_specific_property_info_without_original_url(self, sample_property_payload, sample_redfin_html):
        """Test fallback to create_url when original URL not available."""
        payload_without_url = {k: v for k, v in sample_property_payload.items() if k != 'url'}
        
        with patch('specfic_home_info_helper.fetch_html_via_https') as mock_fetch:
            mock_fetch.return_value = sample_redfin_html
            
            with patch('specfic_home_info_helper.create_url') as mock_create_url:
                mock_create_url.return_value = "https://www.redfin.com/test-url"
                
                result = get_specific_property_info(payload_without_url)
                
                mock_create_url.assert_called_once()
                assert result is not None

    def test_get_specific_property_info_with_relative_url(self, sample_property_payload, sample_redfin_html):
        """Test handling of relative URLs."""
        payload_with_relative_url = sample_property_payload.copy()
        payload_with_relative_url['url'] = "/AZ/Gilbert/123-Main-St-85297/home/12345678"
        
        with patch('specfic_home_info_helper.fetch_html_via_https') as mock_fetch:
            mock_fetch.return_value = sample_redfin_html
            
            result = get_specific_property_info(payload_with_relative_url)
            
            expected_url = "https://www.redfin.com/AZ/Gilbert/123-Main-St-85297/home/12345678"
            mock_fetch.assert_called_once_with(expected_url, Mock())
            assert result is not None

    def test_get_specific_property_info_with_none_html(self, sample_property_payload):
        """Test handling when HTML fetch returns None."""
        with patch('specfic_home_info_helper.fetch_html_via_https') as mock_fetch:
            mock_fetch.return_value = None
            
            result = get_specific_property_info(sample_property_payload)
            
            assert result is None

    def test_get_specific_property_info_with_empty_payload(self):
        """Test handling of empty payload."""
        result = get_specific_property_info({})
        assert result is None

    def test_get_specific_property_info_with_none_payload(self):
        """Test handling of None payload."""
        with pytest.raises((TypeError, AttributeError)):
            get_specific_property_info(None)

    def test_get_specific_property_info_with_exception(self, sample_property_payload):
        """Test handling of exceptions during processing."""
        with patch('specfic_home_info_helper.fetch_html_via_https') as mock_fetch:
            mock_fetch.side_effect = Exception("Network error")
            
            result = get_specific_property_info(sample_property_payload)
            
            assert result is None


class TestGetPropertyJson:
    """Test property JSON parsing functionality."""

    def test_get_property_json_old_structure(self):
        """Test parsing old Redfin HTML structure."""
        html_old_structure = '''
        <html>
        <script type="text/javascript">
        window.__INITIAL_STATE__ = {
            "amenitiesInfo": {
                "superGroups": [{
                    "amenityGroups": [{
                        "amenityEntries": [{
                            "amenityName": "Tax Annual Amount",
                            "amenityValues": ["$1,866"]
                        }]
                    }]
                }]
            }
        };
        </script>
        </html>
        '''
        result = get_property_json(html_old_structure)
        assert result is not None
        assert "amenitiesInfo" in result

    def test_get_property_json_new_structure(self, sample_redfin_html):
        """Test parsing new Redfin HTML structure."""
        result = get_property_json(sample_redfin_html)
        assert result is not None

    def test_get_property_json_with_belowthefold_data(self, sample_redfin_html):
        """Test parsing with belowTheFold data."""
        with patch('specfic_home_info_helper._extract_below_the_fold_data') as mock_extract:
            mock_extract.return_value = {
                "amenitiesInfo": {
                    "superGroups": [{
                        "amenityGroups": [{
                            "amenityEntries": [{
                                "amenityName": "Tax Annual Amount",
                                "amenityValues": ["$1,866"]
                            }]
                        }]
                    }]
                }
            }
            
            result = get_property_json(sample_redfin_html)
            assert result is not None

    def test_get_property_json_with_empty_html(self):
        """Test parsing empty HTML."""
        with pytest.raises(ValueError, match="No script tags found"):
            get_property_json("")

    def test_get_property_json_with_no_script_tags(self):
        """Test parsing HTML without script tags."""
        html_without_scripts = "<html><body>No scripts</body></html>"
        with pytest.raises(ValueError, match="No script tags found"):
            get_property_json(html_without_scripts)

    def test_get_property_json_with_malformed_json(self):
        """Test parsing HTML with malformed JSON."""
        malformed_html = '''
        <html>
        <script type="text/javascript">
        window.__INITIAL_STATE__ = { invalid json };
        </script>
        </html>
        '''
        with pytest.raises(ValueError, match="Could not find any"):
            get_property_json(malformed_html)

    def test_get_property_json_with_undefined_values(self):
        """Test parsing HTML with undefined values."""
        html_with_undefined = '''
        <html>
        <script type="text/javascript">
        window.__INITIAL_STATE__ = {
            "amenitiesInfo": {
                "superGroups": undefined
            }
        };
        </script>
        </html>
        '''
        result = get_property_json(html_with_undefined)
        assert result is not None

    def test_get_property_json_with_nested_quotes(self):
        """Test parsing HTML with nested quotes."""
        html_with_quotes = '''
        <html>
        <script type="text/javascript">
        window.__INITIAL_STATE__ = {
            "description": "This is a \\"quoted\\" description"
        };
        </script>
        </html>
        '''
        result = get_property_json(html_with_quotes)
        assert result is not None
        assert "quoted" in result["description"]


class TestExtractBelowTheFoldData:
    """Test belowTheFold data extraction."""

    def test_extract_belowthefold_data_success(self):
        """Test successful belowTheFold data extraction."""
        html_with_belowthefold = '''
        <html>
        <script type="text/javascript">
        root.__reactServerState.InitialContext = {
            "ReactServerAgent.cache": {
                "dataCache": {
                    "/stingray/api/home/details/belowTheFold": {
                        "res": {
                            "text": "{}&&{\\"payload\\":{\\"amenitiesInfo\\":{\\"superGroups\\":[]}}}"
                        }
                    }
                }
            }
        };
        </script>
        </html>
        '''
        result = _extract_below_the_fold_data(html_with_belowthefold)
        assert result is not None
        assert "amenitiesInfo" in result

    def test_extract_belowthefold_data_not_found(self):
        """Test when belowTheFold data is not found."""
        html_without_belowthefold = '''
        <html>
        <script type="text/javascript">
        root.__reactServerState.InitialContext = {
            "ReactServerAgent.cache": {
                "dataCache": {}
            }
        };
        </script>
        </html>
        '''
        result = _extract_below_the_fold_data(html_without_belowthefold)
        assert result is None

    def test_extract_belowthefold_data_malformed_json(self):
        """Test handling of malformed JSON in belowTheFold data."""
        html_with_malformed = '''
        <html>
        <script type="text/javascript">
        root.__reactServerState.InitialContext = {
            "ReactServerAgent.cache": {
                "dataCache": {
                    "/stingray/api/home/details/belowTheFold": {
                        "res": {
                            "text": "{}&&{ invalid json }"
                        }
                    }
                }
            }
        };
        </script>
        </html>
        '''
        result = _extract_below_the_fold_data(html_with_malformed)
        assert result is None

    def test_extract_belowthefold_data_with_empty_html(self):
        """Test handling of empty HTML."""
        result = _extract_below_the_fold_data("")
        assert result is None


class TestDataExtractionFunctions:
    """Test individual data extraction functions."""

    def test_get_agent_info_with_data(self):
        """Test agent info extraction with valid data."""
        data = {
            "mlsDisclaimerInfo": {
                "listingAgentName": "John Doe",
                "listingBrokerName": "ABC Realty"
            }
        }
        result = get_agent_info(data)
        assert result["agent_name"] == "John Doe"
        assert result["agent_broker"] == "ABC Realty"

    def test_get_agent_info_without_data(self):
        """Test agent info extraction without data."""
        data = {}
        result = get_agent_info(data)
        assert result["agent_name"] is None
        assert result["agent_broker"] is None

    def test_get_schools_with_data(self):
        """Test school extraction with valid data."""
        data = {
            "schoolsAndDistrictsInfo": {
                "servingThisHomeSchools": [
                    {"name": "Test Elementary", "rating": 5, "is_elementary": True},
                    {"name": "Test High School", "rating": 4, "is_elementary": False}
                ]
            }
        }
        result = get_schools(data)
        assert len(result) == 2
        assert result[0]["name"] == "Test Elementary"
        assert result[1]["name"] == "Test High School"

    def test_get_schools_without_data(self):
        """Test school extraction without data."""
        data = {}
        result = get_schools(data)
        assert result == []

    def test_get_price_history_with_data(self):
        """Test price history extraction with valid data."""
        data = {
            "propertyHistoryInfo": {
                "events": [
                    {"price": 500000, "eventDescription": "Sold", "eventDate": 1751007600000},
                    {"price": 480000, "eventDescription": "Listed", "eventDate": 1751007500000}
                ]
            }
        }
        result = get_price_history(data)
        assert len(result) == 2
        assert result[0]["price"] == 500000
        assert result[1]["price"] == 480000

    def test_get_price_history_without_data(self):
        """Test price history extraction without data."""
        data = {}
        result = get_price_history(data)
        assert result == []

    def test_get_covered_spaces_with_data(self):
        """Test covered spaces extraction with valid data."""
        data = {
            "amenitiesInfo": {
                "superGroups": [{
                    "amenityGroups": [{
                        "amenityEntries": [{
                            "amenityName": "Covered Spaces",
                            "amenityValues": ["2"]
                        }]
                    }]
                }]
            }
        }
        result = get_covered_spaces(data)
        assert result == 2

    def test_get_covered_spaces_without_data(self):
        """Test covered spaces extraction without data."""
        data = {}
        result = get_covered_spaces(data)
        assert result is None

    def test_get_tax_annual_with_data(self):
        """Test tax annual extraction with valid data."""
        data = {
            "amenitiesInfo": {
                "superGroups": [{
                    "amenityGroups": [{
                        "amenityEntries": [{
                            "amenityName": "Tax Annual Amount",
                            "amenityValues": ["$1,866"]
                        }]
                    }]
                }]
            }
        }
        result = get_tax_annual(data)
        assert result == 1866

    def test_get_tax_annual_without_data(self):
        """Test tax annual extraction without data."""
        data = {}
        result = get_tax_annual(data)
        assert result is None

    def test_get_tax_annual_with_invalid_format(self):
        """Test tax annual extraction with invalid format."""
        data = {
            "amenitiesInfo": {
                "superGroups": [{
                    "amenityGroups": [{
                        "amenityEntries": [{
                            "amenityName": "Tax Annual Amount",
                            "amenityValues": ["invalid format"]
                        }]
                    }]
                }]
            }
        }
        result = get_tax_annual(data)
        assert result is None


class TestUpsertMoreInfo:
    """Test the main upsert functionality."""

    def test_upsert_more_info_with_none_extra_info(self, mock_session):
        """Test handling of None extra_info."""
        result = upsert_more_info(mock_session, None, 123, 456, True)
        assert result is None

    def test_upsert_more_info_property_not_found(self, mock_session):
        """Test handling when property doesn't exist."""
        mock_session.query.return_value.filter_by.return_value.one.side_effect = Exception("Not found")
        
        with pytest.raises(RuntimeError, match="Property 123 not found"):
            upsert_more_info(mock_session, {"covered_spaces": 2}, 123, 456, True)

    def test_upsert_more_info_listing_not_found(self, mock_session):
        """Test handling when listing doesn't exist."""
        # Mock property exists
        mock_property = Mock()
        mock_property.covered_spaces = None
        mock_property.tax_annual_amount = None
        mock_session.query.return_value.filter_by.return_value.one.return_value = mock_property
        
        # Mock listing doesn't exist
        mock_session.query.return_value.filter_by.side_effect = [
            mock_property,  # First call for property
            Exception("Listing not found")  # Second call for listing
        ]
        
        with pytest.raises(RuntimeError, match="Listing 456 not found"):
            upsert_more_info(mock_session, {"covered_spaces": 2}, 123, 456, True)

    def test_upsert_more_info_success(self, mock_session):
        """Test successful upsert operation."""
        mock_property = Mock()
        mock_property.covered_spaces = None
        mock_property.tax_annual_amount = None
        
        mock_listing = Mock()
        mock_listing.agent_name = None
        mock_listing.broker = None
        
        mock_session.query.return_value.filter_by.return_value.one.return_value = mock_property
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_listing
        
        extra_info = {
            "covered_spaces": 2,
            "tax_annual_amount": 1866,
            "schools": [{"name": "Test School", "rating": 5, "distance": 0.5}],
            "price_history": [{"price": 500000, "date": "2024-01-01"}],
            "agents_name": "Test Agent",
            "agents_broker": "Test Broker"
        }
        
        result = upsert_more_info(mock_session, extra_info, 123, 456, True)
        
        assert result is None  # Function doesn't return anything
        assert mock_property.covered_spaces == 2
        assert mock_property.tax_annual_amount == 1866
        assert mock_listing.agent_name == "Test Agent"
        assert mock_listing.broker == "Test Broker"

    def test_upsert_more_info_with_decimal_values(self, mock_session):
        """Test handling of decimal values."""
        mock_property = Mock()
        mock_property.covered_spaces = None
        mock_property.tax_annual_amount = None
        
        mock_listing = Mock()
        mock_listing.agent_name = None
        mock_listing.broker = None
        
        mock_session.query.return_value.filter_by.return_value.one.return_value = mock_property
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_listing
        
        extra_info = {
            "covered_spaces": 2.5,
            "tax_annual_amount": 1866.50
        }
        
        upsert_more_info(mock_session, extra_info, 123, 456, True)
        
        assert mock_property.covered_spaces == 2  # Should be converted to int
        assert mock_property.tax_annual_amount == 1866  # Should be converted to int

    def test_upsert_more_info_with_invalid_values(self, mock_session):
        """Test handling of invalid values."""
        mock_property = Mock()
        mock_property.covered_spaces = None
        mock_property.tax_annual_amount = None
        
        mock_listing = Mock()
        mock_listing.agent_name = None
        mock_listing.broker = None
        
        mock_session.query.return_value.filter_by.return_value.one.return_value = mock_property
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_listing
        
        extra_info = {
            "covered_spaces": "invalid",
            "tax_annual_amount": "invalid"
        }
        
        upsert_more_info(mock_session, extra_info, 123, 456, True)
        
        # Should handle invalid values gracefully
        assert mock_property.covered_spaces is None
        assert mock_property.tax_annual_amount is None


class TestUpsertSchool:
    """Test school upsert functionality."""

    def test_upsert_school_new_school(self, mock_session):
        """Test creating a new school."""
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        result = upsert_school(mock_session, "Test School", 5, 0.5, 123)
        
        mock_session.add.assert_called()
        assert result is not None

    def test_upsert_school_existing_school(self, mock_session):
        """Test updating an existing school."""
        mock_school = Mock()
        mock_school.school_id = 456
        mock_school.rating = 4
        
        mock_session.query.return_value.filter.return_value.first.return_value = mock_school
        
        result = upsert_school(mock_session, "Test School", 5, 0.5, 123)
        
        assert result == 456
        assert mock_school.rating == 5


class TestUpsertPropertySchool:
    """Test property-school relationship upsert functionality."""

    def test_upsert_property_school_new_relationship(self, mock_session):
        """Test creating a new property-school relationship."""
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        upsert_property_school(mock_session, 123, 456, 0.5)
        
        mock_session.add.assert_called()

    def test_upsert_property_school_existing_relationship(self, mock_session):
        """Test updating an existing property-school relationship."""
        mock_relationship = Mock()
        mock_relationship.distance = 1.0
        
        mock_session.query.return_value.filter.return_value.first.return_value = mock_relationship
        
        upsert_property_school(mock_session, 123, 456, 0.5)
        
        assert mock_relationship.distance == 0.5


class TestBootstrapFunctions:
    """Test bootstrap functionality."""

    def test_bootstrap_price_histories(self, mock_session):
        """Test price history bootstrapping."""
        price_history = [
            {"price": 500000, "eventDate": 1751007600000},
            {"price": 480000, "eventDate": 1751007500000}
        ]
        
        bootstrap_price_histories(mock_session, price_history, 123)
        
        mock_session.add.assert_called()

    def test_bootstrap_sold_histories(self, mock_session):
        """Test sold history bootstrapping."""
        sold_history = [
            {"price": 500000, "eventDate": 1751007600000, "eventDescription": "Sold"}
        ]
        
        bootstrap_sold_histories(mock_session, sold_history, 123)
        
        mock_session.add.assert_called()


class TestCleanPrice:
    """Test price cleaning functionality."""

    def test_clean_price_with_valid_price(self):
        """Test cleaning valid price."""
        result = clean_price("$500,000")
        assert result == 500000

    def test_clean_price_with_none(self):
        """Test cleaning None price."""
        result = clean_price(None)
        assert result is None

    def test_clean_price_with_empty_string(self):
        """Test cleaning empty string."""
        result = clean_price("")
        assert result is None

    def test_clean_price_with_invalid_format(self):
        """Test cleaning invalid price format."""
        result = clean_price("invalid price")
        assert result is None

    def test_clean_price_with_decimal(self):
        """Test cleaning decimal price."""
        result = clean_price("$500,000.50")
        assert result == 500000


class TestCreateUrl:
    """Test URL creation functionality."""

    def test_create_url_valid_input(self):
        """Test URL creation with valid input."""
        url = create_url({
            "address": "123 Main St",
            "city": "Gilbert",
            "state": "AZ",
            "zipcode": "85297",
            "redfin_property_id": "12345678"
        })
        expected = "https://www.redfin.com/AZ/Gilbert/123-Main-St-85297/home/12345678"
        assert url == expected

    def test_create_url_with_special_characters(self):
        """Test URL creation with special characters."""
        url = create_url({
            "address": "123 Main St #101",
            "city": "Gilbert",
            "state": "AZ",
            "zipcode": "85297",
            "redfin_property_id": "12345678"
        })
        expected = "https://www.redfin.com/AZ/Gilbert/123-Main-St-101-85297/home/12345678"
        assert url == expected

    def test_create_url_with_missing_fields(self):
        """Test URL creation with missing fields."""
        with pytest.raises(KeyError):
            create_url({
                "address": "123 Main St",
                "city": "Gilbert"
                # Missing state, zipcode, redfin_property_id
            })


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_large_html(self):
        """Test handling of very large HTML."""
        large_html = "<html><script>window.__INITIAL_STATE__ = {};</script>" + "x" * 1000000 + "</html>"
        
        with pytest.raises(ValueError):  # Expected to fail due to invalid JSON
            get_property_json(large_html)

    def test_html_with_unicode_characters(self):
        """Test handling of unicode characters."""
        unicode_html = '''
        <html>
        <script type="text/javascript">
        window.__INITIAL_STATE__ = {
            "address": {
                "street": "123 Main St 🏠",
                "city": "Gilbert",
                "state": "AZ"
            }
        };
        </script>
        </html>
        '''
        result = get_property_json(unicode_html)
        assert result is not None
        assert result["address"]["street"] == "123 Main St 🏠"

    def test_html_with_nested_quotes(self):
        """Test handling of nested quotes."""
        html_with_quotes = '''
        <html>
        <script type="text/javascript">
        window.__INITIAL_STATE__ = {
            "description": "This is a \\"quoted\\" description with 'single' quotes"
        };
        </script>
        </html>
        '''
        result = get_property_json(html_with_quotes)
        assert result is not None
        assert "quoted" in result["description"]

    def test_multiple_script_tags(self):
        """Test HTML with multiple script tags."""
        html_with_multiple_scripts = '''
        <html>
        <script type="text/javascript">
        var otherData = { "not": "initial_state" };
        </script>
        <script type="text/javascript">
        window.__INITIAL_STATE__ = {
            "amenitiesInfo": {}
        };
        </script>
        </html>
        '''
        result = get_property_json(html_with_multiple_scripts)
        assert result is not None

    def test_script_without_type_attribute(self):
        """Test HTML with script tag without type attribute."""
        html_without_type = '''
        <html>
        <script>
        window.__INITIAL_STATE__ = {
            "amenitiesInfo": {}
        };
        </script>
        </html>
        '''
        result = get_property_json(html_without_type)
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
