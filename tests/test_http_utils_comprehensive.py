"""
Comprehensive tests for utils/http_utils.py including error handling and edge cases.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import requests


class TestMakeRequest:
    """Test the main HTTP request functionality."""

    def test_make_request_success(self):
        """Test successful HTTP request."""
        mock_response = Mock()
        mock_response.text = "<html><body>Success</body></html>"
        mock_response.raise_for_status = Mock()
        
        with patch('requests.get') as mock_get:
            mock_get.return_value = mock_response
            
            from src.utils.http import make_request
            result = make_request("https://example.com")
            
            assert result == "<html><body>Success</body></html>"
            mock_response.raise_for_status.assert_called_once()
            mock_get.assert_called_once_with(
                "https://example.com",
                headers=None,
                proxies=None,
                timeout=20,
                impersonate="chrome110"
            )

    def test_make_request_with_headers(self):
        """Test HTTP request with custom headers."""
        mock_response = Mock()
        mock_response.text = "<html><body>Success</body></html>"
        mock_response.raise_for_status = Mock()
        
        with patch('requests.get') as mock_get:
            mock_get.return_value = mock_response
            
            from src.utils.http import make_request
            headers = {"User-Agent": "Test Agent", "Accept": "text/html"}
            result = make_request("https://example.com", headers=headers)
            
            mock_get.assert_called_once_with(
                "https://example.com",
                headers=headers,
                proxies=None,
                timeout=20,
                impersonate="chrome110"
            )
            assert result == "<html><body>Success</body></html>"

    def test_make_request_with_proxies(self):
        """Test HTTP request with proxies."""
        mock_response = Mock()
        mock_response.text = "<html><body>Success</body></html>"
        mock_response.raise_for_status = Mock()
        
        with patch('requests.get') as mock_get:
            mock_get.return_value = mock_response
            
            from src.utils.http import make_request
            proxies = {"http": "http://proxy:8080", "https": "https://proxy:8080"}
            result = make_request("https://example.com", proxies=proxies)
            
            mock_get.assert_called_once_with(
                "https://example.com",
                headers=None,
                proxies=proxies,
                timeout=20,
                impersonate="chrome110"
            )

    def test_make_request_with_custom_timeout(self):
        """Test HTTP request with custom timeout."""
        mock_response = Mock()
        mock_response.text = "<html><body>Success</body></html>"
        mock_response.raise_for_status = Mock()
        
        with patch('requests.get') as mock_get:
            mock_get.return_value = mock_response
            
            from src.utils.http import make_request
            result = make_request("https://example.com", timeout=30)
            
            mock_get.assert_called_once_with(
                "https://example.com",
                headers=None,
                proxies=None,
                timeout=30,
                impersonate="chrome110"
            )

    def test_make_request_with_http_error(self):
        """Test HTTP request with HTTP error."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        
        with patch('requests.get') as mock_get:
            mock_get.return_value = mock_response
            
            from src.utils.http import make_request
            result = make_request("https://example.com")
            
            assert result is None

    def test_make_request_with_connection_error(self):
        """Test HTTP request with connection error."""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.ConnectionError("Connection failed")
            
            from src.utils.http import make_request
            result = make_request("https://example.com")
            
            assert result is None

    def test_make_request_with_timeout_error(self):
        """Test HTTP request with timeout error."""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.Timeout("Request timed out")
            
            from src.utils.http import make_request
            result = make_request("https://example.com")
            
            assert result is None

    def test_make_request_with_request_exception(self):
        """Test HTTP request with general request exception."""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.RequestException("Request failed")
            
            from src.utils.http import make_request
            result = make_request("https://example.com")
            
            assert result is None

    def test_make_request_with_general_exception(self):
        """Test HTTP request with general exception."""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = Exception("Unexpected error")
            
            from src.utils.http import make_request
            result = make_request("https://example.com")
            
            assert result is None

    def test_make_request_with_invalid_url(self):
        """Test HTTP request with invalid URL."""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = Exception("Invalid URL")
            
            from src.utils.http import make_request
            result = make_request("not-a-valid-url")
            
            assert result is None

    def test_make_request_with_none_url(self):
        """Test HTTP request with None URL."""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = Exception("None URL")
            
            from src.utils.http import make_request
            result = make_request(None)
            
            assert result is None

    def test_make_request_with_empty_url(self):
        """Test HTTP request with empty URL."""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = Exception("Empty URL")
            
            from src.utils.http import make_request
            result = make_request("")
            
            assert result is None


class TestFetchHtmlViaHttps:
    """Test the legacy HTTP fetching functionality."""

    def test_fetch_html_via_https_success(self):
        """Test successful HTML fetching with user agent rotation."""
        with patch('utils.http_utils.make_request') as mock_make_request:
            mock_make_request.return_value = "<html><body>Success</body></html>"
            
            with patch('services.user_agent_service.UserAgentService') as mock_ua_service:
                mock_service = Mock()
                mock_service.get_working_user_agents.return_value = [
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                ]
                mock_ua_service.return_value = mock_service
                
                from src.utils.http import fetch_html_via_https
                result = fetch_html_via_https("https://example.com")
                
                assert result == "<html><body>Success</body></html>"
                mock_make_request.assert_called_once()

    def test_fetch_html_via_https_with_working_user_agent(self):
        """Test HTML fetching with working user agent."""
        with patch('utils.http_utils.make_request') as mock_make_request:
            mock_make_request.side_effect = [None, "<html><body>Success</body></html>"]
            
            with patch('services.user_agent_service.UserAgentService') as mock_ua_service:
                mock_service = Mock()
                mock_service.get_working_user_agents.return_value = [
                    "Failing Agent",
                    "Working Agent"
                ]
                mock_ua_service.return_value = mock_service
                
                from src.utils.http import fetch_html_via_https
                result = fetch_html_via_https("https://example.com")
                
                assert result == "<html><body>Success</body></html>"
                assert mock_make_request.call_count == 2

    def test_fetch_html_via_https_no_working_user_agents(self):
        """Test HTML fetching when no user agents work."""
        with patch('utils.http_utils.make_request') as mock_make_request:
            mock_make_request.return_value = None
            
            with patch('services.user_agent_service.UserAgentService') as mock_ua_service:
                mock_service = Mock()
                mock_service.get_working_user_agents.return_value = [
                    "Failing Agent 1",
                    "Failing Agent 2",
                    "Failing Agent 3"
                ]
                mock_ua_service.return_value = mock_service
                
                from src.utils.http import fetch_html_via_https
                result = fetch_html_via_https("https://example.com")
                
                assert result is None
                assert mock_make_request.call_count == 3

    def test_fetch_html_via_https_no_user_agents_from_database(self):
        """Test HTML fetching when database returns no user agents."""
        with patch('utils.http_utils.make_request') as mock_make_request:
            mock_make_request.return_value = "<html><body>Success</body></html>"
            
            with patch('services.user_agent_service.UserAgentService') as mock_ua_service:
                mock_service = Mock()
                mock_service.get_working_user_agents.return_value = []
                mock_ua_service.return_value = mock_service
                
                from src.utils.http import fetch_html_via_https
                result = fetch_html_via_https("https://example.com")
                
                assert result == "<html><body>Success</body></html>"
                mock_make_request.assert_called_once()

    def test_fetch_html_via_https_database_error(self):
        """Test HTML fetching when database access fails."""
        with patch('utils.http_utils.make_request') as mock_make_request:
            mock_make_request.return_value = "<html><body>Success</body></html>"
            
            with patch('services.user_agent_service.UserAgentService') as mock_ua_service:
                mock_ua_service.side_effect = Exception("Database error")
                
                from src.utils.http import fetch_html_via_https
                result = fetch_html_via_https("https://example.com")
                
                assert result == "<html><body>Success</body></html>"
                mock_make_request.assert_called_once()

    def test_fetch_html_via_https_with_custom_headers(self):
        """Test HTML fetching with custom headers."""
        with patch('utils.http_utils.make_request') as mock_make_request:
            mock_make_request.return_value = "<html><body>Success</body></html>"
            
            with patch('services.user_agent_service.UserAgentService') as mock_ua_service:
                mock_service = Mock()
                mock_service.get_working_user_agents.return_value = [
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                ]
                mock_ua_service.return_value = mock_service
                
                from src.utils.http import fetch_html_via_https
                custom_headers = {"Accept": "text/html", "Accept-Language": "en-US"}
                result = fetch_html_via_https("https://example.com", custom_headers)
                
                # Should merge custom headers with user agent
                expected_headers = {
                    "Accept": "text/html",
                    "Accept-Language": "en-US",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                mock_make_request.assert_called_once_with(
                    "https://example.com",
                    headers=expected_headers,
                    proxies=None
                )

    def test_fetch_html_via_https_with_proxies(self):
        """Test HTML fetching with proxies."""
        with patch('utils.http_utils.make_request') as mock_make_request:
            mock_make_request.return_value = "<html><body>Success</body></html>"
            
            with patch('services.user_agent_service.UserAgentService') as mock_ua_service:
                mock_service = Mock()
                mock_service.get_working_user_agents.return_value = [
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                ]
                mock_ua_service.return_value = mock_service
                
                from src.utils.http import fetch_html_via_https
                proxies = {"http": "http://proxy:8080", "https": "https://proxy:8080"}
                result = fetch_html_via_https("https://example.com", proxy=proxies)
                
                mock_make_request.assert_called_once_with(
                    "https://example.com",
                    headers=Mock(),
                    proxies=proxies
                )

    def test_fetch_html_via_https_with_none_url(self):
        """Test HTML fetching with None URL."""
        with patch('utils.http_utils.make_request') as mock_make_request:
            mock_make_request.return_value = None
            
            from src.utils.http import fetch_html_via_https
            result = fetch_html_via_https(None)
            
            assert result is None

    def test_fetch_html_via_https_with_empty_url(self):
        """Test HTML fetching with empty URL."""
        with patch('utils.http_utils.make_request') as mock_make_request:
            mock_make_request.return_value = None
            
            from src.utils.http import fetch_html_via_https
            result = fetch_html_via_https("")
            
            assert result is None


class TestStripJsonBeginning:
    """Test JSON prefix stripping functionality."""

    def test_strip_json_beginning_valid_prefix(self):
        """Test stripping valid prefix from JSON."""
        from src.utils.http import strip_json_beginning
        
        text = '{}&&{"key": "value"}'
        result = strip_json_beginning(text, '{}&&')
        assert result == '{"key": "value"}'

    def test_strip_json_beginning_without_prefix(self):
        """Test stripping when prefix is not present."""
        from src.utils.http import strip_json_beginning
        
        text = '{"key": "value"}'
        with pytest.raises(ValueError, match="Prefix '{}&&' not found in text"):
            strip_json_beginning(text, '{}&&')

    def test_strip_json_beginning_with_empty_text(self):
        """Test stripping with empty text."""
        from src.utils.http import strip_json_beginning
        
        with pytest.raises(ValueError, match="Prefix '{}&&' not found in text"):
            strip_json_beginning("", '{}&&')

    def test_strip_json_beginning_with_none_text(self):
        """Test stripping with None text."""
        from src.utils.http import strip_json_beginning
        
        with pytest.raises((TypeError, AttributeError)):
            strip_json_beginning(None, '{}&&')

    def test_strip_json_beginning_with_none_prefix(self):
        """Test stripping with None prefix."""
        from src.utils.http import strip_json_beginning
        
        with pytest.raises((TypeError, AttributeError)):
            strip_json_beginning('{"key": "value"}', None)

    def test_strip_json_beginning_with_empty_prefix(self):
        """Test stripping with empty prefix."""
        from src.utils.http import strip_json_beginning
        
        text = '{"key": "value"}'
        result = strip_json_beginning(text, '')
        assert result == '{"key": "value"}'

    def test_strip_json_beginning_with_multiple_prefixes(self):
        """Test stripping with multiple occurrences of prefix."""
        from src.utils.http import strip_json_beginning
        
        text = '{}&&{}&&{"key": "value"}'
        result = strip_json_beginning(text, '{}&&')
        assert result == '{"key": "value"}'

    def test_strip_json_beginning_with_unicode_prefix(self):
        """Test stripping with unicode prefix."""
        from src.utils.http import strip_json_beginning
        
        text = '🏠&&{"key": "value"}'
        result = strip_json_beginning(text, '🏠&&')
        assert result == '{"key": "value"}'

    def test_strip_json_beginning_with_very_long_prefix(self):
        """Test stripping with very long prefix."""
        from src.utils.http import strip_json_beginning
        
        long_prefix = "A" * 1000 + "&&"
        text = long_prefix + '{"key": "value"}'
        result = strip_json_beginning(text, long_prefix)
        assert result == '{"key": "value"}'

    def test_strip_json_beginning_with_very_long_text(self):
        """Test stripping with very long text."""
        from src.utils.http import strip_json_beginning
        
        long_text = '{}&&' + "A" * 10000
        with pytest.raises(ValueError, match="Could not find complete valid JSON after prefix"):
            strip_json_beginning(long_text, '{}&&')


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_make_request_with_very_long_url(self):
        """Test HTTP request with very long URL."""
        long_url = "https://example.com/" + "A" * 10000
        
        with patch('requests.get') as mock_get:
            mock_get.side_effect = Exception("URL too long")
            
            from src.utils.http import make_request
            result = make_request(long_url)
            
            assert result is None

    def test_make_request_with_very_large_headers(self):
        """Test HTTP request with very large headers."""
        large_headers = {"User-Agent": "A" * 10000}
        
        mock_response = Mock()
        mock_response.text = "<html><body>Success</body></html>"
        mock_response.raise_for_status = Mock()
        
        with patch('requests.get') as mock_get:
            mock_get.return_value = mock_response
            
            from src.utils.http import make_request
            result = make_request("https://example.com", headers=large_headers)
            
            assert result == "<html><body>Success</body></html>"

    def test_make_request_with_very_large_response(self):
        """Test HTTP request with very large response."""
        large_response = "<html><body>" + "A" * 1000000 + "</body></html>"
        
        mock_response = Mock()
        mock_response.text = large_response
        mock_response.raise_for_status = Mock()
        
        with patch('requests.get') as mock_get:
            mock_get.return_value = mock_response
            
            from src.utils.http import make_request
            result = make_request("https://example.com")
            
            assert result == large_response

    def test_fetch_html_via_https_with_very_many_user_agents(self):
        """Test HTML fetching with very many user agents."""
        many_user_agents = [f"Agent{i}" for i in range(1000)]
        
        with patch('utils.http_utils.make_request') as mock_make_request:
            mock_make_request.return_value = None
            
            with patch('services.user_agent_service.UserAgentService') as mock_ua_service:
                mock_service = Mock()
                mock_service.get_working_user_agents.return_value = many_user_agents
                mock_ua_service.return_value = mock_service
                
                from src.utils.http import fetch_html_via_https
                result = fetch_html_via_https("https://example.com")
                
                assert result is None
                assert mock_make_request.call_count == 1000

    def test_strip_json_beginning_with_unicode_text(self):
        """Test stripping with unicode text."""
        from src.utils.http import strip_json_beginning
        
        unicode_text = '{}&&{"key": "🏠 value 🚀"}'
        result = strip_json_beginning(unicode_text, '{}&&')
        assert result == '{"key": "🏠 value 🚀"}'

    def test_strip_json_beginning_with_special_characters(self):
        """Test stripping with special characters."""
        from src.utils.http import strip_json_beginning
        
        special_text = '{}&&{"key": "value with \\"quotes\\" and \'apostrophes\'"}'
        result = strip_json_beginning(special_text, '{}&&')
        assert result == '{"key": "value with \\"quotes\\" and \'apostrophes\'"}'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
