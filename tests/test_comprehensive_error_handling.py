"""
Comprehensive error handling and edge case tests for the real estate project.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from job_runner import handle_individual_property_fetch, handle_fetch_zestimate, handle_sold_or_for_sale_homes_fetch
from specfic_home_info_helper import get_specific_property_info, get_property_json, upsert_more_info
from zestimate_helper import get_zestimate, pull_zestimate_from_html, upsert_zestimates
from homes_from_zipcode_helper import fetch_homes_json_from_zipcode
from utils.http_utils import make_request, fetch_html_via_https


class TestErrorHandling:
    """Test comprehensive error handling scenarios."""

    def test_get_specific_property_info_with_none_payload(self):
        """Test handling of None payload."""
        with pytest.raises((TypeError, AttributeError)):
            get_specific_property_info(None)

    def test_get_specific_property_info_with_empty_payload(self):
        """Test handling of empty payload."""
        result = get_specific_property_info({})
        assert result is None

    def test_get_specific_property_info_with_missing_url(self, sample_property_payload):
        """Test handling when URL is missing and create_url fails."""
        payload = {k: v for k, v in sample_property_payload.items() if k != 'url'}
        payload['city'] = None  # This will cause create_url to fail
        
        with patch('specfic_home_info_helper.fetch_html_via_https') as mock_fetch:
            mock_fetch.return_value = None
            result = get_specific_property_info(payload)
            assert result is None

    def test_get_property_json_with_empty_html(self):
        """Test handling of empty HTML."""
        with pytest.raises(ValueError, match="No script tags found"):
            get_property_json("")

    def test_get_property_json_with_invalid_html(self):
        """Test handling of invalid HTML."""
        invalid_html = "<html><body>No script tags</body></html>"
        with pytest.raises(ValueError, match="No script tags found"):
            get_property_json(invalid_html)

    def test_get_property_json_with_malformed_json(self):
        """Test handling of malformed JSON in script tags."""
        malformed_html = '''
        <html>
        <script type="text/javascript">
        window.__INITIAL_STATE__ = { invalid json };
        </script>
        </html>
        '''
        with pytest.raises(ValueError, match="Could not find any"):
            get_property_json(malformed_html)

    def test_get_property_json_with_new_structure_but_no_belowthefold(self):
        """Test handling when new structure exists but no belowTheFold data."""
        html_with_new_structure = '''
        <html>
        <script type="text/javascript">
        root.__reactServerState.InitialContext = {
            "ReactServerAgent.cache": {
                "dataCache": {
                    "/stingray/api/home/details/aboveTheFold": {
                        "res": {"text": "{}&&{\\"version\\":608}"}
                    }
                }
            }
        };
        </script>
        </html>
        '''
        with patch('specfic_home_info_helper._extract_below_the_fold_data') as mock_extract:
            mock_extract.return_value = None
            result = get_property_json(html_with_new_structure)
            # Should return the aboveTheFold data even if belowTheFold is missing
            assert result is not None

    def test_upsert_more_info_with_none_extra_info(self, mock_session):
        """Test handling of None extra_info."""
        result = upsert_more_info(mock_session, None, 123, 456, True)
        assert result is None

    def test_upsert_more_info_with_missing_property(self, mock_session):
        """Test handling when property doesn't exist in database."""
        mock_session.query.return_value.filter_by.return_value.one.side_effect = Exception("Not found")
        
        with pytest.raises(RuntimeError, match="Property 123 not found"):
            upsert_more_info(mock_session, {"covered_spaces": 2}, 123, 456, True)

    def test_upsert_more_info_with_missing_listing(self, mock_session, sample_property_payload):
        """Test handling when listing doesn't exist in database."""
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

    def test_get_zestimate_with_none_address(self):
        """Test handling of None address."""
        with pytest.raises(ValueError, match="All address components"):
            get_zestimate(None, "Gilbert", "AZ", "85297")

    def test_get_zestimate_with_empty_address(self):
        """Test handling of empty address."""
        with pytest.raises(ValueError, match="All address components"):
            get_zestimate("", "Gilbert", "AZ", "85297")

    def test_get_zestimate_with_invalid_address_components(self):
        """Test handling of invalid address components."""
        with pytest.raises(ValueError, match="All address components"):
            get_zestimate("123 Main St", None, "AZ", "85297")

    def test_pull_zestimate_from_html_with_empty_html(self):
        """Test handling of empty HTML in zestimate parsing."""
        with pytest.raises(ValueError, match="Empty HTML provided"):
            pull_zestimate_from_html("")

    def test_pull_zestimate_from_html_with_no_initial_state(self):
        """Test handling of HTML without INITIAL_STATE."""
        html_without_state = "<html><body>No INITIAL_STATE</body></html>"
        with pytest.raises(ValueError, match="Could not find any"):
            pull_zestimate_from_html(html_without_state)

    def test_pull_zestimate_from_html_with_malformed_json(self):
        """Test handling of malformed JSON in INITIAL_STATE."""
        malformed_html = '''
        <html>
        <script type="text/javascript">
        window.__INITIAL_STATE__ = { invalid json };
        </script>
        </html>
        '''
        with pytest.raises(ValueError, match="Could not find any"):
            pull_zestimate_from_html(malformed_html)

    def test_pull_zestimate_from_html_with_none_zestimate(self):
        """Test handling when zestimate is None in the data."""
        html_with_none_zestimate = '''
        <html>
        <script type="text/javascript">
        window.__INITIAL_STATE__ = {
            "address": {
                "rentZestimate": null,
                "rentZestimateRangeHigh": null,
                "rentZestimateRangeLow": null
            }
        };
        </script>
        </html>
        '''
        result = pull_zestimate_from_html(html_with_none_zestimate)
        assert result == (None, None, None)

    def test_upsert_zestimates_with_missing_property(self, mock_session):
        """Test handling when property doesn't exist for zestimate update."""
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        
        upsert_zestimates(mock_session, 999999, 2500, 2700, 2300)
        # Should not raise an error, just log and return

    def test_handle_individual_property_fetch_with_none_payload(self):
        """Test handling of None payload in job handler."""
        with pytest.raises((TypeError, AttributeError)):
            handle_individual_property_fetch(None)

    def test_handle_individual_property_fetch_with_missing_keys(self):
        """Test handling of payload with missing required keys."""
        incomplete_payload = {"address": "123 Main St"}
        
        with patch('job_runner.get_specific_property_info') as mock_get_info:
            mock_get_info.return_value = None
            # Should not raise an error, just handle gracefully
            handle_individual_property_fetch(incomplete_payload)

    def test_handle_fetch_zestimate_with_none_payload(self):
        """Test handling of None payload in zestimate handler."""
        with pytest.raises((TypeError, AttributeError)):
            handle_fetch_zestimate(None)

    def test_handle_fetch_zestimate_with_missing_keys(self):
        """Test handling of payload with missing required keys."""
        incomplete_payload = {"address": "123 Main St"}
        
        with patch('job_runner.get_zestimate') as mock_get_zestimate:
            mock_get_zestimate.return_value = (None, None, None)
            # Should not raise an error, just handle gracefully
            handle_fetch_zestimate(incomplete_payload)

    def test_fetch_homes_json_from_zipcode_with_invalid_zipcode(self):
        """Test handling of invalid zipcode."""
        result = fetch_homes_json_from_zipcode("invalid_zipcode", "for_sale")
        assert result == []

    def test_fetch_homes_json_from_zipcode_with_none_zipcode(self):
        """Test handling of None zipcode."""
        with pytest.raises((TypeError, AttributeError)):
            fetch_homes_json_from_zipcode(None, "for_sale")

    def test_make_request_with_invalid_url(self):
        """Test handling of invalid URL in HTTP requests."""
        result = make_request("not-a-valid-url")
        assert result is None

    def test_make_request_with_timeout(self):
        """Test handling of request timeout."""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = Exception("Timeout")
            result = make_request("https://httpbin.org/delay/10", timeout=1)
            assert result is None

    def test_make_request_with_connection_error(self):
        """Test handling of connection errors."""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = Exception("Connection error")
            result = make_request("https://example.com")
            assert result is None

    def test_fetch_html_via_https_with_no_working_user_agents(self):
        """Test handling when no user agents work."""
        with patch('utils.http_utils.make_request') as mock_request:
            mock_request.return_value = None
            result = fetch_html_via_https("https://example.com")
            assert result is None

    def test_handle_sold_or_for_sale_homes_fetch_with_invalid_payload(self):
        """Test handling of invalid payload in homes fetch handler."""
        invalid_payload = {"invalid": "data"}
        
        with pytest.raises((KeyError, TypeError)):
            handle_sold_or_for_sale_homes_fetch("for_sale", invalid_payload)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_property_json_with_very_large_html(self):
        """Test handling of very large HTML."""
        large_html = "<html><script>window.__INITIAL_STATE__ = {};</script>" + "x" * 1000000 + "</html>"
        # Should not crash with large HTML
        with pytest.raises(ValueError):  # Expected to fail due to invalid JSON
            get_property_json(large_html)

    def test_zestimate_with_very_large_numbers(self):
        """Test handling of very large zestimate numbers."""
        html_with_large_numbers = '''
        <html>
        <script type="text/javascript">
        window.__INITIAL_STATE__ = {
            "address": {
                "rentZestimate": 999999999999,
                "rentZestimateRangeHigh": 999999999999,
                "rentZestimateRangeLow": 999999999999
            }
        };
        </script>
        </html>
        '''
        result = pull_zestimate_from_html(html_with_large_numbers)
        assert result == (999999999999, 999999999999, 999999999999)

    def test_property_json_with_unicode_characters(self):
        """Test handling of unicode characters in HTML."""
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

    def test_zestimate_with_special_characters_in_address(self):
        """Test handling of special characters in address."""
        result = get_zestimate("123 Main St #101", "Gilbert", "AZ", "85297")
        # Should handle special characters gracefully
        assert result is not None or result == (None, None, None)

    def test_property_json_with_nested_quotes(self):
        """Test handling of nested quotes in JSON."""
        html_with_nested_quotes = '''
        <html>
        <script type="text/javascript">
        window.__INITIAL_STATE__ = {
            "description": "This is a \\"quoted\\" description with 'single' quotes"
        };
        </script>
        </html>
        '''
        result = get_property_json(html_with_nested_quotes)
        assert result is not None
        assert "quoted" in result["description"]

    def test_upsert_with_decimal_covered_spaces(self):
        """Test handling of decimal covered spaces."""
        with patch('specfic_home_info_helper.Property') as mock_property_class:
            mock_property = Mock()
            mock_property.covered_spaces = None
            mock_property.tax_annual_amount = None
            
            mock_session = Mock()
            mock_session.query.return_value.filter_by.return_value.one.return_value = mock_property
            mock_session.query.return_value.filter_by.return_value.first.return_value = Mock()
            
            upsert_more_info(mock_session, {"covered_spaces": 2.5}, 123, 456, True)
            # Should handle decimal values gracefully

    def test_upsert_with_negative_tax_amount(self):
        """Test handling of negative tax amount."""
        with patch('specfic_home_info_helper.Property') as mock_property_class:
            mock_property = Mock()
            mock_property.covered_spaces = None
            mock_property.tax_annual_amount = None
            
            mock_session = Mock()
            mock_session.query.return_value.filter_by.return_value.one.return_value = mock_property
            mock_session.query.return_value.filter_by.return_value.first.return_value = Mock()
            
            upsert_more_info(mock_session, {"tax_annual_amount": -100}, 123, 456, True)
            # Should handle negative values (though unlikely in real data)

    def test_zestimate_with_zero_values(self):
        """Test handling of zero zestimate values."""
        html_with_zero_values = '''
        <html>
        <script type="text/javascript">
        window.__INITIAL_STATE__ = {
            "address": {
                "rentZestimate": 0,
                "rentZestimateRangeHigh": 0,
                "rentZestimateRangeLow": 0
            }
        };
        </script>
        </html>
        '''
        result = pull_zestimate_from_html(html_with_zero_values)
        assert result == (0, 0, 0)


class TestConcurrencyAndRaceConditions:
    """Test scenarios that might occur in concurrent environments."""

    def test_concurrent_property_updates(self, mock_session):
        """Test handling of concurrent property updates."""
        # This is a simplified test - in reality, you'd use threading or asyncio
        with patch('specfic_home_info_helper.Property') as mock_property_class:
            mock_property = Mock()
            mock_property.covered_spaces = None
            mock_property.tax_annual_amount = None
            
            mock_session.query.return_value.filter_by.return_value.one.return_value = mock_property
            mock_session.query.return_value.filter_by.return_value.first.return_value = Mock()
            
            # Simulate concurrent updates
            upsert_more_info(mock_session, {"covered_spaces": 2}, 123, 456, True)
            upsert_more_info(mock_session, {"covered_spaces": 3}, 123, 456, True)
            
            # Should handle gracefully without crashing

    def test_database_connection_loss(self, mock_session):
        """Test handling of database connection loss."""
        mock_session.commit.side_effect = Exception("Connection lost")
        
        with pytest.raises(Exception):
            upsert_more_info(mock_session, {"covered_spaces": 2}, 123, 456, True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
