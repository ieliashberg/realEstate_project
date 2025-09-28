"""
Comprehensive tests for user_agent_service.py including error handling and edge cases.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta

from services.user_agent_service import UserAgentService
from models.user_agent import UserAgent


class TestUserAgentService:
    """Test the main UserAgentService functionality."""

    def test_init_with_session(self, mock_session):
        """Test UserAgentService initialization with session."""
        service = UserAgentService(mock_session)
        assert service.session == mock_session

    def test_init_without_session(self):
        """Test UserAgentService initialization without session."""
        with patch('services.user_agent_service.SessionLocal') as mock_session_local:
            mock_session = Mock()
            mock_session_local.return_value = mock_session
            
            service = UserAgentService()
            assert service.session == mock_session

    def test_scrape_new_user_agents_success(self):
        """Test successful user agent scraping."""
        mock_html = '''
        <html>
        <textarea id="most-common-desktop-useragents-json-csv">
        [
            {"ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            {"ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        ]
        </textarea>
        </html>
        '''
        
        with patch('services.user_agent_service.make_request') as mock_request:
            mock_request.return_value = mock_html
            
            service = UserAgentService(Mock())
            result = service.scrape_new_user_agents()
            
            assert len(result) == 2
            assert "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" in result[0]
            assert "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)" in result[1]

    def test_scrape_new_user_agents_old_format(self):
        """Test user agent scraping with old format."""
        mock_html = '''
        <html>
        <textarea id="most-common-desktop-useragents-json-csv">
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        </textarea>
        </html>
        '''
        
        with patch('services.user_agent_service.make_request') as mock_request:
            mock_request.return_value = mock_html
            
            service = UserAgentService(Mock())
            result = service.scrape_new_user_agents()
            
            assert len(result) == 2
            assert "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" in result[0]

    def test_scrape_new_user_agents_no_textarea(self):
        """Test user agent scraping when textarea is not found."""
        mock_html = '<html><body>No textarea</body></html>'
        
        with patch('services.user_agent_service.make_request') as mock_request:
            mock_request.return_value = mock_html
            
            service = UserAgentService(Mock())
            result = service.scrape_new_user_agents()
            
            assert result == []

    def test_scrape_new_user_agents_request_failure(self):
        """Test user agent scraping when request fails."""
        with patch('services.user_agent_service.make_request') as mock_request:
            mock_request.return_value = None
            
            service = UserAgentService(Mock())
            result = service.scrape_new_user_agents()
            
            assert result == []

    def test_scrape_new_user_agents_exception(self):
        """Test user agent scraping when exception occurs."""
        with patch('services.user_agent_service.make_request') as mock_request:
            mock_request.side_effect = Exception("Network error")
            
            service = UserAgentService(Mock())
            result = service.scrape_new_user_agents()
            
            assert result == []

    def test_scrape_new_user_agents_malformed_json(self):
        """Test user agent scraping with malformed JSON."""
        mock_html = '''
        <html>
        <textarea id="most-common-desktop-useragents-json-csv">
        [ invalid json ]
        </textarea>
        </html>
        '''
        
        with patch('services.user_agent_service.make_request') as mock_request:
            mock_request.return_value = mock_html
            
            service = UserAgentService(Mock())
            result = service.scrape_new_user_agents()
            
            # Should fall back to old format parsing
            assert result == []

    def test_scrape_new_user_agents_mixed_format(self):
        """Test user agent scraping with mixed format data."""
        mock_html = '''
        <html>
        <textarea id="most-common-desktop-useragents-json-csv">
        [
            {"ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        ]
        </textarea>
        </html>
        '''
        
        with patch('services.user_agent_service.make_request') as mock_request:
            mock_request.return_value = mock_html
            
            service = UserAgentService(Mock())
            result = service.scrape_new_user_agents()
            
            assert len(result) == 2

    def test_scrape_new_user_agents_limit(self):
        """Test user agent scraping with limit."""
        mock_html = '''
        <html>
        <textarea id="most-common-desktop-useragents-json-csv">
        [
            {"ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            {"ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
            {"ua": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
        ]
        </textarea>
        </html>
        '''
        
        with patch('services.user_agent_service.make_request') as mock_request:
            mock_request.return_value = mock_html
            
            service = UserAgentService(Mock())
            result = service.scrape_new_user_agents()
            
            assert len(result) == 3  # Should return all, limit is applied in the method


class TestUserAgentTesting:
    """Test user agent testing functionality."""

    def test_test_user_agent_success(self):
        """Test successful user agent testing."""
        mock_response = '''
        {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        '''
        
        with patch('services.user_agent_service.make_request') as mock_request:
            mock_request.return_value = mock_response
            
            service = UserAgentService(Mock())
            result = service.test_user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            
            assert result is True

    def test_test_user_agent_failure(self):
        """Test failed user agent testing."""
        with patch('services.user_agent_service.make_request') as mock_request:
            mock_request.return_value = None
            
            service = UserAgentService(Mock())
            result = service.test_user_agent("Invalid User Agent")
            
            assert result is False

    def test_test_user_agent_mismatch(self):
        """Test user agent testing with mismatched response."""
        mock_response = '''
        {
            "user-agent": "Different User Agent"
        }
        '''
        
        with patch('services.user_agent_service.make_request') as mock_request:
            mock_request.return_value = mock_response
            
            service = UserAgentService(Mock())
            result = service.test_user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            
            assert result is False

    def test_test_user_agent_malformed_json(self):
        """Test user agent testing with malformed JSON response."""
        mock_response = "invalid json"
        
        with patch('services.user_agent_service.make_request') as mock_request:
            mock_request.return_value = mock_response
            
            service = UserAgentService(Mock())
            result = service.test_user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            
            assert result is True  # Falls back to length check

    def test_test_user_agent_short_response(self):
        """Test user agent testing with short response."""
        mock_response = "short"
        
        with patch('services.user_agent_service.make_request') as mock_request:
            mock_request.return_value = mock_response
            
            service = UserAgentService(Mock())
            result = service.test_user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            
            assert result is False

    def test_test_user_agent_exception(self):
        """Test user agent testing when exception occurs."""
        with patch('services.user_agent_service.make_request') as mock_request:
            mock_request.side_effect = Exception("Network error")
            
            service = UserAgentService(Mock())
            result = service.test_user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            
            assert result is False

    def test_test_user_agent_custom_url(self):
        """Test user agent testing with custom URL."""
        with patch('services.user_agent_service.make_request') as mock_request:
            mock_request.return_value = "valid response"
            
            service = UserAgentService(Mock())
            result = service.test_user_agent("Test Agent", "https://custom-test-url.com")
            
            mock_request.assert_called_once_with("https://custom-test-url.com", 
                                                {"User-Agent": "Test Agent"}, 
                                                timeout=10)


class TestUserAgentDatabaseOperations:
    """Test user agent database operations."""

    def test_import_user_agents_new(self, mock_session):
        """Test importing new user agents."""
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        service = UserAgentService(mock_session)
        user_agents = ["Agent1", "Agent2", "Agent3"]
        
        service.import_user_agents(user_agents)
        
        assert mock_session.add.call_count == 3
        mock_session.commit.assert_called_once()

    def test_import_user_agents_existing(self, mock_session):
        """Test importing existing user agents."""
        mock_existing_agent = Mock()
        mock_session.query.return_value.filter.return_value.first.return_value = mock_existing_agent
        
        service = UserAgentService(mock_session)
        user_agents = ["ExistingAgent"]
        
        service.import_user_agents(user_agents)
        
        mock_session.add.assert_not_called()
        mock_session.commit.assert_called_once()

    def test_import_user_agents_empty_list(self, mock_session):
        """Test importing empty user agent list."""
        service = UserAgentService(mock_session)
        
        service.import_user_agents([])
        
        mock_session.add.assert_not_called()
        mock_session.commit.assert_called_once()

    def test_import_user_agents_none_list(self, mock_session):
        """Test importing None user agent list."""
        service = UserAgentService(mock_session)
        
        with pytest.raises((TypeError, AttributeError)):
            service.import_user_agents(None)

    def test_import_user_agents_database_error(self, mock_session):
        """Test importing user agents with database error."""
        mock_session.add.side_effect = Exception("Database error")
        
        service = UserAgentService(mock_session)
        user_agents = ["Agent1"]
        
        with pytest.raises(Exception, match="Database error"):
            service.import_user_agents(user_agents)

    def test_update_user_agent_status_working(self, mock_session):
        """Test updating user agent status to working."""
        mock_user_agent = Mock()
        mock_user_agent.status = "unknown"
        mock_session.query.return_value.filter.return_value.first.return_value = mock_user_agent
        
        service = UserAgentService(mock_session)
        
        service.update_user_agent_status("Test Agent", True)
        
        assert mock_user_agent.status == "working"
        assert mock_user_agent.last_tested is not None
        mock_session.commit.assert_called_once()

    def test_update_user_agent_status_failing(self, mock_session):
        """Test updating user agent status to failing."""
        mock_user_agent = Mock()
        mock_user_agent.status = "working"
        mock_session.query.return_value.filter.return_value.first.return_value = mock_user_agent
        
        service = UserAgentService(mock_session)
        
        service.update_user_agent_status("Test Agent", False)
        
        assert mock_user_agent.status == "failing"
        assert mock_user_agent.last_tested is not None
        mock_session.commit.assert_called_once()

    def test_update_user_agent_status_not_found(self, mock_session):
        """Test updating status for non-existent user agent."""
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        service = UserAgentService(mock_session)
        
        service.update_user_agent_status("Non-existent Agent", True)
        
        mock_session.commit.assert_called_once()

    def test_update_user_agent_status_database_error(self, mock_session):
        """Test updating user agent status with database error."""
        mock_session.commit.side_effect = Exception("Database error")
        
        service = UserAgentService(mock_session)
        
        with pytest.raises(Exception, match="Database error"):
            service.update_user_agent_status("Test Agent", True)

    def test_get_working_user_agents(self, mock_session):
        """Test getting working user agents."""
        mock_working_agents = [Mock(), Mock(), Mock()]
        mock_session.query.return_value.filter.return_value.limit.return_value.all.return_value = mock_working_agents
        
        service = UserAgentService(mock_session)
        
        result = service.get_working_user_agents(5)
        
        assert len(result) == 3
        mock_session.query.assert_called()

    def test_get_working_user_agents_none_found(self, mock_session):
        """Test getting working user agents when none found."""
        mock_session.query.return_value.filter.return_value.limit.return_value.all.return_value = []
        
        service = UserAgentService(mock_session)
        
        result = service.get_working_user_agents(5)
        
        assert result == []

    def test_cleanup_old_user_agents(self, mock_session):
        """Test cleaning up old user agents."""
        mock_old_agents = [Mock(), Mock()]
        mock_session.query.return_value.filter.return_value.all.return_value = mock_old_agents
        
        service = UserAgentService(mock_session)
        
        result = service.cleanup_old_user_agents(30)
        
        assert result == 2
        assert mock_session.delete.call_count == 2
        mock_session.commit.assert_called_once()

    def test_cleanup_old_user_agents_none_found(self, mock_session):
        """Test cleaning up old user agents when none found."""
        mock_session.query.return_value.filter.return_value.all.return_value = []
        
        service = UserAgentService(mock_session)
        
        result = service.cleanup_old_user_agents(30)
        
        assert result == 0
        mock_session.delete.assert_not_called()
        mock_session.commit.assert_called_once()

    def test_cleanup_old_user_agents_database_error(self, mock_session):
        """Test cleaning up old user agents with database error."""
        mock_session.delete.side_effect = Exception("Database error")
        mock_old_agents = [Mock()]
        mock_session.query.return_value.filter.return_value.all.return_value = mock_old_agents
        
        service = UserAgentService(mock_session)
        
        with pytest.raises(Exception, match="Database error"):
            service.cleanup_old_user_agents(30)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_scrape_new_user_agents_with_unicode_characters(self):
        """Test scraping user agents with unicode characters."""
        mock_html = '''
        <html>
        <textarea id="most-common-desktop-useragents-json-csv">
        [
            {"ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 🚀"}
        ]
        </textarea>
        </html>
        '''
        
        with patch('services.user_agent_service.make_request') as mock_request:
            mock_request.return_value = mock_html
            
            service = UserAgentService(Mock())
            result = service.scrape_new_user_agents()
            
            assert len(result) == 1
            assert "🚀" in result[0]

    def test_scrape_new_user_agents_with_very_long_user_agent(self):
        """Test scraping very long user agents."""
        long_user_agent = "A" * 10000
        
        mock_html = f'''
        <html>
        <textarea id="most-common-desktop-useragents-json-csv">
        [
            {{"ua": "{long_user_agent}"}}
        ]
        </textarea>
        </html>
        '''
        
        with patch('services.user_agent_service.make_request') as mock_request:
            mock_request.return_value = mock_html
            
            service = UserAgentService(Mock())
            result = service.scrape_new_user_agents()
            
            assert len(result) == 1
            assert len(result[0]) == 10000

    def test_test_user_agent_with_very_long_user_agent(self):
        """Test testing very long user agent."""
        long_user_agent = "A" * 10000
        
        with patch('services.user_agent_service.make_request') as mock_request:
            mock_request.return_value = f'{{"user-agent": "{long_user_agent}"}}'
            
            service = UserAgentService(Mock())
            result = service.test_user_agent(long_user_agent)
            
            assert result is True

    def test_import_user_agents_with_duplicates(self, mock_session):
        """Test importing user agents with duplicates."""
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        service = UserAgentService(mock_session)
        user_agents = ["Agent1", "Agent1", "Agent2"]  # Duplicate Agent1
        
        service.import_user_agents(user_agents)
        
        # Should still add all three (database handles uniqueness)
        assert mock_session.add.call_count == 3

    def test_import_user_agents_with_empty_strings(self, mock_session):
        """Test importing user agents with empty strings."""
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        service = UserAgentService(mock_session)
        user_agents = ["", "Valid Agent", ""]
        
        service.import_user_agents(user_agents)
        
        assert mock_session.add.call_count == 3

    def test_import_user_agents_with_none_values(self, mock_session):
        """Test importing user agents with None values."""
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        service = UserAgentService(mock_session)
        user_agents = [None, "Valid Agent", None]
        
        service.import_user_agents(user_agents)
        
        assert mock_session.add.call_count == 3

    def test_update_user_agent_status_with_none_user_agent(self, mock_session):
        """Test updating status with None user agent."""
        service = UserAgentService(mock_session)
        
        with pytest.raises((TypeError, AttributeError)):
            service.update_user_agent_status(None, True)

    def test_update_user_agent_status_with_empty_user_agent(self, mock_session):
        """Test updating status with empty user agent."""
        service = UserAgentService(mock_session)
        
        service.update_user_agent_status("", True)
        
        mock_session.commit.assert_called_once()

    def test_get_working_user_agents_with_zero_limit(self, mock_session):
        """Test getting working user agents with zero limit."""
        service = UserAgentService(mock_session)
        
        result = service.get_working_user_agents(0)
        
        assert result == []
        mock_session.query.assert_called()

    def test_get_working_user_agents_with_negative_limit(self, mock_session):
        """Test getting working user agents with negative limit."""
        service = UserAgentService(mock_session)
        
        result = service.get_working_user_agents(-1)
        
        assert result == []
        mock_session.query.assert_called()

    def test_cleanup_old_user_agents_with_zero_days(self, mock_session):
        """Test cleaning up old user agents with zero days."""
        service = UserAgentService(mock_session)
        
        result = service.cleanup_old_user_agents(0)
        
        assert result == 0
        mock_session.query.assert_called()

    def test_cleanup_old_user_agents_with_negative_days(self, mock_session):
        """Test cleaning up old user agents with negative days."""
        service = UserAgentService(mock_session)
        
        result = service.cleanup_old_user_agents(-1)
        
        assert result == 0
        mock_session.query.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
