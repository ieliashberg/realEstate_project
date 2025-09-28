"""
Comprehensive tests for zestimate_helper.py including error handling and edge cases.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from zestimate_helper import (
    get_zestimate,
    pull_zestimate_from_html,
    upsert_zestimates,
    create_url,
    _is_valid_zestimate_page,
    fetch_html_for_zestimate_via_playwright,
    _try_http_request,
    _try_playwright_request
)


class TestCreateUrl:
    """Test URL creation functionality."""

    def test_create_url_valid_input(self):
        """Test URL creation with valid input."""
        url = create_url("123 Main St", "Gilbert", "AZ", "85297")
        expected = "https://www.zillow.com/rental-manager/price-my-rental/results/123-main-st-gilbert-az-85297/"
        assert url == expected

    def test_create_url_with_special_characters(self):
        """Test URL creation with special characters."""
        url = create_url("123 Main St #101", "Gilbert", "AZ", "85297")
        expected = "https://www.zillow.com/rental-manager/price-my-rental/results/123-main-st-101-gilbert-az-85297/"
        assert url == expected

    def test_create_url_with_none_address(self):
        """Test URL creation with None address."""
        with pytest.raises(ValueError, match="All address components"):
            create_url(None, "Gilbert", "AZ", "85297")

    def test_create_url_with_empty_address(self):
        """Test URL creation with empty address."""
        with pytest.raises(ValueError, match="All address components"):
            create_url("", "Gilbert", "AZ", "85297")

    def test_create_url_with_missing_city(self):
        """Test URL creation with missing city."""
        with pytest.raises(ValueError, match="All address components"):
            create_url("123 Main St", None, "AZ", "85297")

    def test_create_url_with_missing_state(self):
        """Test URL creation with missing state."""
        with pytest.raises(ValueError, match="All address components"):
            create_url("123 Main St", "Gilbert", None, "85297")

    def test_create_url_with_missing_zipcode(self):
        """Test URL creation with missing zipcode."""
        with pytest.raises(ValueError, match="All address components"):
            create_url("123 Main St", "Gilbert", "AZ", None)

    def test_create_url_with_whitespace(self):
        """Test URL creation with whitespace in components."""
        url = create_url("  123 Main St  ", "  Gilbert  ", "  AZ  ", "  85297  ")
        expected = "https://www.zillow.com/rental-manager/price-my-rental/results/123-main-st-gilbert-az-85297/"
        assert url == expected

    def test_create_url_with_unicode_characters(self):
        """Test URL creation with unicode characters."""
        url = create_url("123 Main St 🏠", "Gilbert", "AZ", "85297")
        expected = "https://www.zillow.com/rental-manager/price-my-rental/results/123-main-st-🏠-gilbert-az-85297/"
        assert url == expected


class TestPullZestimateFromHtml:
    """Test zestimate parsing from HTML."""

    def test_pull_zestimate_valid_html(self, sample_zillow_html):
        """Test parsing valid Zillow HTML."""
        result = pull_zestimate_from_html(sample_zillow_html)
        assert result == (2500, 2700, 2300)

    def test_pull_zestimate_with_none_values(self):
        """Test parsing HTML with None zestimate values."""
        html_with_none = '''
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
        result = pull_zestimate_from_html(html_with_none)
        assert result == (None, None, None)

    def test_pull_zestimate_with_zero_values(self):
        """Test parsing HTML with zero zestimate values."""
        html_with_zero = '''
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
        result = pull_zestimate_from_html(html_with_zero)
        assert result == (0, 0, 0)

    def test_pull_zestimate_with_empty_html(self):
        """Test parsing empty HTML."""
        with pytest.raises(ValueError, match="Empty HTML provided"):
            pull_zestimate_from_html("")

    def test_pull_zestimate_with_none_html(self):
        """Test parsing None HTML."""
        with pytest.raises(ValueError, match="Empty HTML provided"):
            pull_zestimate_from_html(None)

    def test_pull_zestimate_with_no_script_tags(self):
        """Test parsing HTML without script tags."""
        html_without_scripts = "<html><body>No scripts</body></html>"
        with pytest.raises(ValueError, match="Could not find any"):
            pull_zestimate_from_html(html_without_scripts)

    def test_pull_zestimate_with_no_initial_state(self):
        """Test parsing HTML without INITIAL_STATE."""
        html_without_state = '''
        <html>
        <script type="text/javascript">
        var otherData = { "not": "initial_state" };
        </script>
        </html>
        '''
        with pytest.raises(ValueError, match="Could not find any"):
            pull_zestimate_from_html(html_without_state)

    def test_pull_zestimate_with_malformed_json(self):
        """Test parsing HTML with malformed JSON."""
        html_with_malformed_json = '''
        <html>
        <script type="text/javascript">
        window.__INITIAL_STATE__ = { invalid json };
        </script>
        </html>
        '''
        with pytest.raises(ValueError, match="Could not find any"):
            pull_zestimate_from_html(html_with_malformed_json)

    def test_pull_zestimate_with_undefined_values(self):
        """Test parsing HTML with undefined values."""
        html_with_undefined = '''
        <html>
        <script type="text/javascript">
        window.__INITIAL_STATE__ = {
            "address": {
                "rentZestimate": undefined,
                "rentZestimateRangeHigh": undefined,
                "rentZestimateRangeLow": undefined
            }
        };
        </script>
        </html>
        '''
        result = pull_zestimate_from_html(html_with_undefined)
        assert result == (None, None, None)

    def test_pull_zestimate_with_mixed_data_types(self):
        """Test parsing HTML with mixed data types."""
        html_with_mixed = '''
        <html>
        <script type="text/javascript">
        window.__INITIAL_STATE__ = {
            "address": {
                "rentZestimate": "2500",
                "rentZestimateRangeHigh": 2700.5,
                "rentZestimateRangeLow": "2300"
            }
        };
        </script>
        </html>
        '''
        result = pull_zestimate_from_html(html_with_mixed)
        assert result == (2500, 2700.5, 2300)

    def test_pull_zestimate_with_very_large_numbers(self):
        """Test parsing HTML with very large numbers."""
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


class TestIsValidZestimatePage:
    """Test zestimate page validation."""

    def test_is_valid_with_rentzestimate(self):
        """Test validation with valid zestimate page."""
        html = "<html><body>This page has rentzestimate data</body></html>"
        assert _is_valid_zestimate_page(html) is True

    def test_is_valid_without_rentzestimate(self):
        """Test validation with invalid page."""
        html = "<html><body>This is a captcha page</body></html>"
        assert _is_valid_zestimate_page(html) is False

    def test_is_valid_with_empty_html(self):
        """Test validation with empty HTML."""
        assert _is_valid_zestimate_page("") is False

    def test_is_valid_with_none_html(self):
        """Test validation with None HTML."""
        assert _is_valid_zestimate_page(None) is False

    def test_is_valid_case_insensitive(self):
        """Test validation is case insensitive."""
        html = "<html><body>This page has RENTZESTIMATE data</body></html>"
        assert _is_valid_zestimate_page(html) is True

    def test_is_valid_with_multiple_occurrences(self):
        """Test validation with multiple occurrences of rentzestimate."""
        html = "<html><body>rentzestimate data rentzestimate more</body></html>"
        assert _is_valid_zestimate_page(html) is True


class TestUpsertZestimates:
    """Test zestimate database operations."""

    def test_upsert_zestimates_new_property(self, mock_session):
        """Test upserting zestimate for new property."""
        mock_property = Mock()
        mock_property.current_zestimate = None
        mock_property.current_zestimate_high = None
        mock_property.current_zestimate_low = None
        mock_property.property_id = 12345
        
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_property
        
        upsert_zestimates(mock_session, 12345, 2500, 2700, 2300)
        
        assert mock_property.current_zestimate == 2500
        assert mock_property.current_zestimate_high == 2700
        assert mock_property.current_zestimate_low == 2300

    def test_upsert_zestimates_existing_property_with_changes(self, mock_session):
        """Test upserting zestimate for existing property with changes."""
        mock_property = Mock()
        mock_property.current_zestimate = 2400
        mock_property.current_zestimate_high = 2600
        mock_property.current_zestimate_low = 2200
        mock_property.property_id = 12345
        
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_property
        
        upsert_zestimates(mock_session, 12345, 2500, 2700, 2300)
        
        assert mock_property.current_zestimate == 2500
        assert mock_property.current_zestimate_high == 2700
        assert mock_property.current_zestimate_low == 2300

    def test_upsert_zestimates_existing_property_no_changes(self, mock_session):
        """Test upserting zestimate for existing property with no significant changes."""
        mock_property = Mock()
        mock_property.current_zestimate = 2500
        mock_property.current_zestimate_high = 2700
        mock_property.current_zestimate_low = 2300
        mock_property.property_id = 12345
        
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_property
        
        upsert_zestimates(mock_session, 12345, 2501, 2701, 2301)  # Small changes
        
        # Values should remain unchanged due to buffer
        assert mock_property.current_zestimate == 2500
        assert mock_property.current_zestimate_high == 2700
        assert mock_property.current_zestimate_low == 2300

    def test_upsert_zestimates_property_not_found(self, mock_session):
        """Test upserting zestimate for non-existent property."""
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        
        upsert_zestimates(mock_session, 999999, 2500, 2700, 2300)
        # Should not raise an error, just log and return

    def test_upsert_zestimates_with_none_values(self, mock_session):
        """Test upserting zestimate with None values."""
        mock_property = Mock()
        mock_property.current_zestimate = None
        mock_property.current_zestimate_high = None
        mock_property.current_zestimate_low = None
        mock_property.property_id = 12345
        
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_property
        
        upsert_zestimates(mock_session, 12345, None, None, None)
        
        # Should handle None values gracefully
        assert mock_property.current_zestimate is None
        assert mock_property.current_zestimate_high is None
        assert mock_property.current_zestimate_low is None


class TestGetZestimate:
    """Test main zestimate fetching functionality."""

    def test_get_zestimate_success_http(self):
        """Test successful zestimate fetch via HTTP."""
        with patch('zestimate_helper._try_http_request') as mock_http:
            mock_http.return_value = '''
            <html>
            <script type="text/javascript">
            window.__INITIAL_STATE__ = {
                "address": {
                    "rentZestimate": 2500,
                    "rentZestimateRangeHigh": 2700,
                    "rentZestimateRangeLow": 2300
                }
            };
            </script>
            </html>
            '''
            
            with patch('zestimate_helper._try_playwright_request') as mock_playwright:
                result = get_zestimate("123 Main St", "Gilbert", "AZ", "85297")
                
                assert result == (2500, 2700, 2300)
                mock_http.assert_called_once()
                mock_playwright.assert_not_called()

    def test_get_zestimate_success_playwright_fallback(self):
        """Test successful zestimate fetch via Playwright fallback."""
        with patch('zestimate_helper._try_http_request') as mock_http:
            mock_http.return_value = None
            
            with patch('zestimate_helper._try_playwright_request') as mock_playwright:
                mock_playwright.return_value = '''
                <html>
                <script type="text/javascript">
                window.__INITIAL_STATE__ = {
                    "address": {
                        "rentZestimate": 2500,
                        "rentZestimateRangeHigh": 2700,
                        "rentZestimateRangeLow": 2300
                    }
                };
                </script>
                </html>
                '''
                
                result = get_zestimate("123 Main St", "Gilbert", "AZ", "85297")
                
                assert result == (2500, 2700, 2300)
                mock_http.assert_called_once()
                mock_playwright.assert_called_once()

    def test_get_zestimate_no_data_available(self):
        """Test zestimate fetch when no data is available."""
        with patch('zestimate_helper._try_http_request') as mock_http:
            mock_http.return_value = '''
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
            
            with patch('zestimate_helper._try_playwright_request') as mock_playwright:
                result = get_zestimate("123 Main St", "Gilbert", "AZ", "85297")
                
                assert result == (None, None, None)

    def test_get_zestimate_invalid_page(self):
        """Test zestimate fetch with invalid page (captcha)."""
        with patch('zestimate_helper._try_http_request') as mock_http:
            mock_http.return_value = "<html><body>This is a captcha page</body></html>"
            
            with patch('zestimate_helper._try_playwright_request') as mock_playwright:
                mock_playwright.return_value = "<html><body>This is also a captcha page</body></html>"
                
                result = get_zestimate("123 Main St", "Gilbert", "AZ", "85297")
                
                assert result == (None, None, None)

    def test_get_zestimate_no_html_received(self):
        """Test zestimate fetch when no HTML is received."""
        with patch('zestimate_helper._try_http_request') as mock_http:
            mock_http.return_value = None
            
            with patch('zestimate_helper._try_playwright_request') as mock_playwright:
                mock_playwright.return_value = None
                
                result = get_zestimate("123 Main St", "Gilbert", "AZ", "85297")
                
                assert result == (None, None, None)

    def test_get_zestimate_parsing_error(self):
        """Test zestimate fetch when HTML parsing fails."""
        with patch('zestimate_helper._try_http_request') as mock_http:
            mock_http.return_value = "<html><body>Invalid HTML</body></html>"
            
            with patch('zestimate_helper._try_playwright_request') as mock_playwright:
                mock_playwright.return_value = "<html><body>Also invalid</body></html>"
                
                result = get_zestimate("123 Main St", "Gilbert", "AZ", "85297")
                
                assert result == (None, None, None)

    def test_get_zestimate_with_invalid_address(self):
        """Test zestimate fetch with invalid address."""
        with pytest.raises(ValueError, match="All address components"):
            get_zestimate(None, "Gilbert", "AZ", "85297")


class TestHttpRequest:
    """Test HTTP request functionality."""

    def test_try_http_request_success(self):
        """Test successful HTTP request."""
        with patch('zestimate_helper.make_request') as mock_request:
            mock_request.return_value = "<html><body>Success</body></html>"
            
            result = _try_http_request("https://example.com")
            
            assert result == "<html><body>Success</body></html>"
            mock_request.assert_called_once()

    def test_try_http_request_failure(self):
        """Test failed HTTP request."""
        with patch('zestimate_helper.make_request') as mock_request:
            mock_request.return_value = None
            
            result = _try_http_request("https://example.com")
            
            assert result is None
            mock_request.assert_called_once()


class TestPlaywrightRequest:
    """Test Playwright request functionality."""

    def test_try_playwright_request_success(self, mock_playwright):
        """Test successful Playwright request."""
        result = _try_playwright_request("https://example.com")
        
        assert result == "<html><body>Test HTML</body></html>"

    def test_try_playwright_request_failure(self):
        """Test failed Playwright request."""
        with patch('zestimate_helper.fetch_html_for_zestimate_via_playwright') as mock_fetch:
            mock_fetch.return_value = None
            
            result = _try_playwright_request("https://example.com")
            
            assert result is None

    def test_fetch_html_for_zestimate_via_playwright_with_exception(self):
        """Test Playwright fetch with exception."""
        with patch('zestimate_helper.sync_playwright') as mock_pw:
            mock_pw.side_effect = Exception("Playwright error")
            
            result = fetch_html_for_zestimate_via_playwright("https://example.com")
            
            assert result is None


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_large_html(self):
        """Test handling of very large HTML."""
        large_html = "<html><script>window.__INITIAL_STATE__ = {};</script>" + "x" * 1000000 + "</html>"
        
        with pytest.raises(ValueError):  # Expected to fail due to invalid JSON
            pull_zestimate_from_html(large_html)

    def test_html_with_unicode_escape_sequences(self):
        """Test HTML with unicode escape sequences."""
        html_with_unicode = '''
        <html>
        <script type="text/javascript">
        window.__INITIAL_STATE__ = {
            "address": {
                "street": "123 Main St \\u0020 Gilbert"
            }
        };
        </script>
        </html>
        '''
        result = pull_zestimate_from_html(html_with_unicode)
        assert result is not None

    def test_html_with_comments(self):
        """Test HTML with comments in script tags."""
        html_with_comments = '''
        <html>
        <script type="text/javascript">
        // This is a comment
        window.__INITIAL_STATE__ = {
            "address": {
                "rentZestimate": 2500
            }
        };
        /* Another comment */
        </script>
        </html>
        '''
        result = pull_zestimate_from_html(html_with_comments)
        assert result == (2500, None, None)

    def test_multiple_script_tags(self):
        """Test HTML with multiple script tags."""
        html_with_multiple_scripts = '''
        <html>
        <script type="text/javascript">
        var otherData = { "not": "initial_state" };
        </script>
        <script type="text/javascript">
        window.__INITIAL_STATE__ = {
            "address": {
                "rentZestimate": 2500
            }
        };
        </script>
        </html>
        '''
        result = pull_zestimate_from_html(html_with_multiple_scripts)
        assert result == (2500, None, None)

    def test_script_without_type_attribute(self):
        """Test HTML with script tag without type attribute."""
        html_without_type = '''
        <html>
        <script>
        window.__INITIAL_STATE__ = {
            "address": {
                "rentZestimate": 2500
            }
        };
        </script>
        </html>
        '''
        result = pull_zestimate_from_html(html_without_type)
        assert result == (2500, None, None)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
