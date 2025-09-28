"""
Simple tests for utils/http_utils.py focusing on core functionality.
"""

import pytest
from unittest.mock import Mock, patch


class TestMakeRequest:
    """Test the main HTTP request functionality."""

    def test_make_request_success(self):
        """Test successful HTTP request."""
        mock_response = Mock()
        mock_response.text = "<html><body>Success</body></html>"
        mock_response.raise_for_status = Mock()
        
        with patch('curl_cffi.requests.get') as mock_get:
            mock_get.return_value = mock_response
            
            from utils.http_utils import make_request
            result = make_request("https://example.com")
            
            assert result == "<html><body>Success</body></html>"
            mock_response.raise_for_status.assert_called_once()

    def test_make_request_with_headers(self):
        """Test HTTP request with custom headers."""
        mock_response = Mock()
        mock_response.text = "<html><body>Success</body></html>"
        mock_response.raise_for_status = Mock()
        
        with patch('curl_cffi.requests.get') as mock_get:
            mock_get.return_value = mock_response
            
            from utils.http_utils import make_request
            headers = {"User-Agent": "Test Agent"}
            result = make_request("https://example.com", headers=headers)
            
            mock_get.assert_called_once_with(
                "https://example.com",
                headers=headers,
                proxies=None,
                timeout=20,
                impersonate="chrome110"
            )
            assert result == "<html><body>Success</body></html>"

    def test_make_request_with_http_error(self):
        """Test HTTP request with HTTP error."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("404 Not Found")
        
        with patch('curl_cffi.requests.get') as mock_get:
            mock_get.return_value = mock_response
            
            from utils.http_utils import make_request
            result = make_request("https://example.com")
            
            assert result is None

    def test_make_request_with_connection_error(self):
        """Test HTTP request with connection error."""
        with patch('curl_cffi.requests.get') as mock_get:
            mock_get.side_effect = Exception("Connection failed")
            
            from utils.http_utils import make_request
            result = make_request("https://example.com")
            
            assert result is None


class TestStripJsonBeginning:
    """Test JSON prefix stripping functionality."""

    def test_strip_json_beginning_valid_prefix(self):
        """Test stripping valid prefix from JSON."""
        from utils.http_utils import strip_json_beginning
        
        text = '{}&&{"key": "value"}'
        result = strip_json_beginning(text, '{}&&')
        assert result == '{"key": "value"}'

    def test_strip_json_beginning_without_prefix(self):
        """Test stripping when prefix is not present."""
        from utils.http_utils import strip_json_beginning
        
        text = '{"key": "value"}'
        with pytest.raises(ValueError, match="Prefix '{}&&' not found in text"):
            strip_json_beginning(text, '{}&&')

    def test_strip_json_beginning_with_empty_text(self):
        """Test stripping with empty text."""
        from utils.http_utils import strip_json_beginning
        
        with pytest.raises(ValueError, match="Prefix '{}&&' not found in text"):
            strip_json_beginning("", '{}&&')

    def test_strip_json_beginning_with_none_text(self):
        """Test stripping with None text."""
        from utils.http_utils import strip_json_beginning
        
        with pytest.raises((TypeError, AttributeError)):
            strip_json_beginning(None, '{}&&')

    def test_strip_json_beginning_with_empty_prefix(self):
        """Test stripping with empty prefix."""
        from utils.http_utils import strip_json_beginning
        
        text = '{"key": "value"}'
        result = strip_json_beginning(text, '')
        assert result == '{"key": "value"}'

    def test_strip_json_beginning_with_unicode_prefix(self):
        """Test stripping with unicode prefix."""
        from utils.http_utils import strip_json_beginning
        
        text = '🏠&&{"key": "value"}'
        result = strip_json_beginning(text, '🏠&&')
        assert result == '{"key": "value"}'


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
                
                from utils.http_utils import fetch_html_via_https
                result = fetch_html_via_https("https://example.com")
                
                assert result == "<html><body>Success</body></html>"
                mock_make_request.assert_called_once()

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
                
                from utils.http_utils import fetch_html_via_https
                result = fetch_html_via_https("https://example.com")
                
                assert result is None
                assert mock_make_request.call_count == 3

    def test_fetch_html_via_https_database_error(self):
        """Test HTML fetching when database access fails."""
        with patch('utils.http_utils.make_request') as mock_make_request:
            mock_make_request.return_value = "<html><body>Success</body></html>"
            
            with patch('services.user_agent_service.UserAgentService') as mock_ua_service:
                mock_ua_service.side_effect = Exception("Database error")
                
                from utils.http_utils import fetch_html_via_https
                result = fetch_html_via_https("https://example.com")
                
                assert result == "<html><body>Success</body></html>"
                mock_make_request.assert_called_once()

    def test_fetch_html_via_https_with_none_url(self):
        """Test HTML fetching with None URL."""
        with patch('utils.http_utils.make_request') as mock_make_request:
            mock_make_request.return_value = None
            
            from utils.http_utils import fetch_html_via_https
            result = fetch_html_via_https(None)
            
            assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
