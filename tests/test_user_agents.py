import unittest
from unittest.mock import patch, Mock, MagicMock
import sys
import os

# Add the project directory to the path so we can import the modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.scrapers.user_agents.service import UserAgentService
from src.scrapers.user_agents.models import UserAgent


class TestUserAgentService(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.mock_session = Mock()
        self.service = UserAgentService(self.mock_session)
    
    def test_get_working_user_agents_returns_list(self):
        """Test that get_working_user_agents returns a list."""
        # Mock database query to return empty list
        self.mock_session.query.return_value.filter.return_value.limit.return_value.all.return_value = []
        
        result = self.service.get_working_user_agents()
        self.assertIsInstance(result, list)
    
    def test_get_working_user_agents_with_data(self):
        """Test that get_working_user_agents returns user agents from database."""
        # Mock database query to return some user agents
        mock_ua1 = Mock()
        mock_ua1.user_agent = "Mozilla/5.0 (Test) AppleWebKit/537.36"
        mock_ua2 = Mock()
        mock_ua2.user_agent = "Mozilla/5.0 (Test2) AppleWebKit/537.36"
        
        self.mock_session.query.return_value.filter.return_value.limit.return_value.all.return_value = [mock_ua1, mock_ua2]
        
        result = self.service.get_working_user_agents()
        self.assertEqual(len(result), 2)
        self.assertIn("Mozilla/5.0 (Test) AppleWebKit/537.36", result)
        self.assertIn("Mozilla/5.0 (Test2) AppleWebKit/537.36", result)
    
    def test_get_working_user_agents_empty_database(self):
        """Test that get_working_user_agents returns empty list when no data."""
        self.mock_session.query.return_value.filter.return_value.limit.return_value.all.return_value = []
        
        result = self.service.get_working_user_agents()
        self.assertEqual(result, [])
    
    def test_test_user_agent_success(self):
        """Test that test_user_agent returns True for working user agent."""
        with patch('utils.http_utils.make_request') as mock_request:
            mock_request.return_value = "Valid HTML content" * 10  # More than 100 chars
            
            result = self.service.test_user_agent("test-user-agent")
            self.assertTrue(result)
    
    def test_test_user_agent_failure(self):
        """Test that test_user_agent returns False for failing user agent."""
        with patch('utils.http_utils.make_request') as mock_request:
            mock_request.side_effect = Exception("Request failed")
            
            result = self.service.test_user_agent("test-user-agent")
            self.assertFalse(result)
    
    def test_update_user_agent_status_new(self):
        """Test updating status for new user agent."""
        self.mock_session.query.return_value.filter.return_value.first.return_value = None
        
        self.service.update_user_agent_status("new-user-agent", True)
        
        # Should add new user agent
        self.mock_session.add.assert_called_once()
        self.mock_session.commit.assert_called_once()
    
    def test_update_user_agent_status_existing(self):
        """Test updating status for existing user agent."""
        mock_ua = Mock()
        mock_ua.fail_count = 0
        self.mock_session.query.return_value.filter.return_value.first.return_value = mock_ua
        
        self.service.update_user_agent_status("existing-user-agent", False)
        
        # Should update existing user agent
        self.assertEqual(mock_ua.fail_count, 1)
        self.assertEqual(mock_ua.status, 'failing')
        self.mock_session.commit.assert_called_once()
    
    def test_import_user_agents(self):
        """Test importing new user agents."""
        user_agents = ["UA1", "UA2", "UA3"]
        
        # Mock that no user agents exist
        self.mock_session.query.return_value.filter.return_value.first.return_value = None
        
        self.service.import_user_agents(user_agents)
        
        # Should add 3 new user agents
        self.assertEqual(self.mock_session.add.call_count, 3)
        self.mock_session.commit.assert_called_once()
    
    def test_cleanup_old_user_agents(self):
        """Test cleanup of old user agents."""
        mock_ua1 = Mock()
        mock_ua2 = Mock()
        self.mock_session.query.return_value.filter.return_value.all.return_value = [mock_ua1, mock_ua2]
        
        deleted_count = self.service.cleanup_old_user_agents()
        
        # Should delete 2 user agents
        self.assertEqual(deleted_count, 2)
        self.assertEqual(self.mock_session.delete.call_count, 2)
        self.mock_session.commit.assert_called_once()


if __name__ == '__main__':
    unittest.main()