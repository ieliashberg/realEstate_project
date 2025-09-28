import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
import sys
import os

# Add the project directory to the path so we can import the modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from job_table_helper import enqueue_job
from dataBase import Pipline_Tables


class TestJobTableHelper(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.mock_session = Mock()
        self.sample_pipeline_name = "test_pipeline"
        self.sample_payload = {
            "property_id": 123,
            "address": "123 Main St",
            "city": "San Francisco",
            "state": "CA",
            "zipcode": "94102"
        }

    @patch('job_table_helper.datetime')
    def test_enqueue_job_success(self, mock_datetime):
        """Test successful job enqueuing."""
        # Setup
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = now
        
        # Execute
        enqueue_job(self.mock_session, self.sample_pipeline_name, self.sample_payload)
        
        # Verify
        self.mock_session.add.assert_called_once()
        self.mock_session.commit.assert_called_once()
        
        # Check that the added object is a Pipline_Tables instance
        added_job = self.mock_session.add.call_args[0][0]
        self.assertIsInstance(added_job, Pipline_Tables)
        self.assertEqual(added_job.name_of_pipeline, self.sample_pipeline_name)
        self.assertEqual(added_job.payload, self.sample_payload)
        self.assertEqual(added_job.enqueued_at, now)

    def test_enqueue_job_with_empty_payload(self):
        """Test job enqueuing with empty payload."""
        empty_payload = {}
        
        # Execute
        enqueue_job(self.mock_session, self.sample_pipeline_name, empty_payload)
        
        # Verify
        self.mock_session.add.assert_called_once()
        self.mock_session.commit.assert_called_once()
        
        added_job = self.mock_session.add.call_args[0][0]
        self.assertEqual(added_job.payload, empty_payload)

    def test_enqueue_job_with_none_payload(self):
        """Test job enqueuing with None payload."""
        # Execute
        enqueue_job(self.mock_session, self.sample_pipeline_name, None)
        
        # Verify
        self.mock_session.add.assert_called_once()
        self.mock_session.commit.assert_called_once()
        
        added_job = self.mock_session.add.call_args[0][0]
        self.assertIsNone(added_job.payload)

    def test_enqueue_job_with_complex_payload(self):
        """Test job enqueuing with complex nested payload."""
        complex_payload = {
            "property_id": 123,
            "address": {
                "street": "123 Main St",
                "city": "San Francisco",
                "state": "CA",
                "zipcode": "94102"
            },
            "features": ["pool", "garage", "garden"],
            "metadata": {
                "source": "redfin",
                "timestamp": "2025-01-15T12:00:00Z",
                "priority": 1
            }
        }
        
        # Execute
        enqueue_job(self.mock_session, self.sample_pipeline_name, complex_payload)
        
        # Verify
        self.mock_session.add.assert_called_once()
        self.mock_session.commit.assert_called_once()
        
        added_job = self.mock_session.add.call_args[0][0]
        self.assertEqual(added_job.payload, complex_payload)

    def test_enqueue_job_with_long_pipeline_name(self):
        """Test job enqueuing with long pipeline name."""
        long_pipeline_name = "very_long_pipeline_name_that_might_test_boundaries"
        
        # Execute
        enqueue_job(self.mock_session, long_pipeline_name, self.sample_payload)
        
        # Verify
        self.mock_session.add.assert_called_once()
        self.mock_session.commit.assert_called_once()
        
        added_job = self.mock_session.add.call_args[0][0]
        self.assertEqual(added_job.name_of_pipeline, long_pipeline_name)

    def test_enqueue_job_session_error_handling(self):
        """Test that session errors are properly propagated."""
        # Setup - make commit raise an exception
        self.mock_session.commit.side_effect = Exception("Database error")
        
        # Execute and verify exception is raised
        with self.assertRaises(Exception) as context:
            enqueue_job(self.mock_session, self.sample_pipeline_name, self.sample_payload)
        
        self.assertEqual(str(context.exception), "Database error")

    def test_enqueue_job_add_error_handling(self):
        """Test that add errors are properly propagated."""
        # Setup - make add raise an exception
        self.mock_session.add.side_effect = Exception("Add error")
        
        # Execute and verify exception is raised
        with self.assertRaises(Exception) as context:
            enqueue_job(self.mock_session, self.sample_pipeline_name, self.sample_payload)
        
        self.assertEqual(str(context.exception), "Add error")

    @patch('job_table_helper.datetime')
    def test_enqueue_job_multiple_calls(self, mock_datetime):
        """Test multiple job enqueuing calls."""
        # Setup
        now1 = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        now2 = datetime(2025, 1, 15, 12, 1, 0, tzinfo=timezone.utc)
        mock_datetime.now.side_effect = [now1, now2]
        
        payload1 = {"id": 1}
        payload2 = {"id": 2}
        
        # Execute
        enqueue_job(self.mock_session, "pipeline1", payload1)
        enqueue_job(self.mock_session, "pipeline2", payload2)
        
        # Verify
        self.assertEqual(self.mock_session.add.call_count, 2)
        self.assertEqual(self.mock_session.commit.call_count, 2)
        
        # Check first job
        first_job = self.mock_session.add.call_args_list[0][0][0]
        self.assertEqual(first_job.name_of_pipeline, "pipeline1")
        self.assertEqual(first_job.payload, payload1)
        self.assertEqual(first_job.enqueued_at, now1)
        
        # Check second job
        second_job = self.mock_session.add.call_args_list[1][0][0]
        self.assertEqual(second_job.name_of_pipeline, "pipeline2")
        self.assertEqual(second_job.payload, payload2)
        self.assertEqual(second_job.enqueued_at, now2)


if __name__ == '__main__':
    unittest.main()
