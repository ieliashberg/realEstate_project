import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
import sys
import os

# Add the project directory to the path so we can import the modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.pipeline.runner import process_pipeline_jobs, PIPELINE_HANDLERS
from src.database.connection import Pipline_Tables


class TestJobRunner(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.mock_session = Mock()
        
    def create_job_mock(self, job_id, name_of_pipeline, payload):
        """Helper method to create a job mock with specified attributes."""
        mock_job = Mock(spec=Pipline_Tables)
        mock_job.id = job_id
        mock_job.name_of_pipeline = name_of_pipeline
        mock_job.payload = payload
        return mock_job

    @patch('job_runner.SessionLocal')
    def test_no_jobs_to_process(self, mock_session_local):
        """Test behavior when no jobs are in the queue."""
        # Setup - no jobs in queue
        mock_session = Mock()
        mock_session.query.return_value.order_by.return_value.first.return_value = None
        mock_session_local.return_value = mock_session
        
        # Execute
        process_pipeline_jobs()
        
        # Verify
        mock_session.query.assert_called_once_with(Pipline_Tables)
        mock_session.query.return_value.order_by.assert_called_once_with(Pipline_Tables.id)
        mock_session.close.assert_called_once()

    @patch('job_runner.SessionLocal')
    @patch('job_runner.PIPELINE_HANDLERS')
    def test_successful_job_processing(self, mock_handlers, mock_session_local):
        """Test successful processing of a job with known handler."""
        # Setup - one job with known handler
        job = self.create_job_mock(1, "individual_property_fetch", {"property_id": "123"})
        
        mock_session = Mock()
        mock_session.query.return_value.order_by.return_value.first.side_effect = [job, None]
        mock_session_local.return_value = mock_session
        
        # Mock the handler to succeed
        mock_handler = Mock()
        mock_handlers.get.return_value = mock_handler
        
        # Execute
        process_pipeline_jobs()
        
        # Verify job was processed and deleted
        mock_session.delete.assert_called_once_with(job)
        mock_session.commit.assert_called_once()
        self.assertEqual(mock_session.close.call_count, 2)  # Called twice (once per iteration)

    @patch('job_runner.SessionLocal')
    def test_unknown_handler_job_deletion(self, mock_session_local):
        """Test that jobs with unknown handlers are deleted."""
        # Setup - job with unknown handler
        job = self.create_job_mock(1, "unknown_pipeline", {"data": "test"})
        
        mock_session = Mock()
        mock_session.query.return_value.order_by.return_value.first.side_effect = [job, None]
        mock_session_local.return_value = mock_session
        
        # Execute
        process_pipeline_jobs()
        
        # Verify unknown job was deleted
        mock_session.delete.assert_called_once_with(job)
        mock_session.commit.assert_called_once()
        self.assertEqual(mock_session.close.call_count, 2)

    @patch('job_runner.SessionLocal')
    @patch('job_runner.PIPELINE_HANDLERS')
    def test_job_processing_error_handling(self, mock_handlers, mock_session_local):
        """Test error handling when job processing fails."""
        # Setup - job that will raise an exception
        job = self.create_job_mock(1, "individual_property_fetch", {"property_id": "123"})
        
        mock_session = Mock()
        mock_session.query.return_value.order_by.return_value.first.side_effect = [job, None]
        mock_session_local.return_value = mock_session
        
        # Mock the handler to raise an exception
        mock_handler = Mock()
        mock_handler.side_effect = Exception("Test error")
        mock_handlers.get.return_value = mock_handler
        
        # Execute
        process_pipeline_jobs()
        
        # Verify job was NOT deleted (left for retry)
        mock_session.delete.assert_not_called()
        mock_session.rollback.assert_called_once()
        self.assertEqual(mock_session.close.call_count, 2)

    @patch('job_runner.SessionLocal')
    @patch('job_runner.PIPELINE_HANDLERS')
    def test_multiple_jobs_processing(self, mock_handlers, mock_session_local):
        """Test processing multiple jobs in sequence."""
        # Setup - multiple jobs
        job1 = self.create_job_mock(1, "individual_property_fetch", {"property_id": "123"})
        job2 = self.create_job_mock(2, "fetch_zestimate", {"property_id": "456"})
        job3 = self.create_job_mock(3, "unknown_pipeline", {"data": "test"})
        
        mock_session = Mock()
        mock_session.query.return_value.order_by.return_value.first.side_effect = [job1, job2, job3, None]
        mock_session_local.return_value = mock_session
        
        # Mock the handlers to succeed
        mock_handler = Mock()
        mock_handlers.get.return_value = mock_handler
        
        # Execute
        process_pipeline_jobs()
        
        # Verify all jobs were processed
        self.assertEqual(mock_session.delete.call_count, 3)
        self.assertEqual(mock_session.commit.call_count, 3)
        self.assertEqual(mock_session.close.call_count, 4)  # Called 4 times (once per iteration)

    @patch('job_runner.SessionLocal')
    @patch('job_runner.PIPELINE_HANDLERS')
    def test_sold_homes_fetch_handler_call(self, mock_handlers, mock_session_local):
        """Test that sold_homes_fetch jobs call handler with correct parameters."""
        # Setup - sold homes fetch job
        job = self.create_job_mock(1, "sold_homes_fetch", {"zipcode": "12345"})
        
        mock_session = Mock()
        mock_session.query.return_value.order_by.return_value.first.side_effect = [job, None]
        mock_session_local.return_value = mock_session
        
        # Mock the handler to succeed
        mock_handler = Mock()
        mock_handlers.get.return_value = mock_handler
        
        # Execute
        process_pipeline_jobs()
        
        # Verify handler was called with correct parameters (including session)
        mock_handler.assert_called_once_with("sold_homes_fetch", {"zipcode": "12345"}, mock_session)

    @patch('job_runner.SessionLocal')
    @patch('job_runner.PIPELINE_HANDLERS')
    def test_for_sale_homes_fetch_handler_call(self, mock_handlers, mock_session_local):
        """Test that for_sale_homes_fetch jobs call handler with correct parameters."""
        # Setup - for sale homes fetch job
        job = self.create_job_mock(1, "for_sale_homes_fetch", {"zipcode": "67890"})
        
        mock_session = Mock()
        mock_session.query.return_value.order_by.return_value.first.side_effect = [job, None]
        mock_session_local.return_value = mock_session
        
        # Mock the handler to succeed
        mock_handler = Mock()
        mock_handlers.get.return_value = mock_handler
        
        # Execute
        process_pipeline_jobs()
        
        # Verify handler was called with correct parameters (including session)
        mock_handler.assert_called_once_with("for_sale_homes_fetch", {"zipcode": "67890"}, mock_session)

    @patch('job_runner.SessionLocal')
    @patch('job_runner.PIPELINE_HANDLERS')
    def test_other_handler_call(self, mock_handlers, mock_session_local):
        """Test that other job types call handler with only payload parameter."""
        # Setup - other job type
        job = self.create_job_mock(1, "fetch_zestimate", {"property_id": "123"})
        
        mock_session = Mock()
        mock_session.query.return_value.order_by.return_value.first.side_effect = [job, None]
        mock_session_local.return_value = mock_session
        
        # Mock the handler to succeed
        mock_handler = Mock()
        mock_handlers.get.return_value = mock_handler
        
        # Execute
        process_pipeline_jobs()
        
        # Verify handler was called with only payload
        mock_handler.assert_called_once_with({"property_id": "123"})

    @patch('job_runner.SessionLocal')
    @patch('job_runner.PIPELINE_HANDLERS')
    def test_session_management_on_success(self, mock_handlers, mock_session_local):
        """Test proper session management when job succeeds."""
        # Setup
        job = self.create_job_mock(1, "individual_property_fetch", {"property_id": "123"})
        
        mock_session = Mock()
        mock_session.query.return_value.order_by.return_value.first.side_effect = [job, None]
        mock_session_local.return_value = mock_session
        
        # Mock the handler to succeed
        mock_handler = Mock()
        mock_handlers.get.return_value = mock_handler
        
        # Execute
        process_pipeline_jobs()
        
        # Verify session management
        mock_session_local.assert_called()  # Session was created
        mock_session.commit.assert_called()  # Changes were committed
        mock_session.close.assert_called()   # Session was closed

    @patch('job_runner.SessionLocal')
    @patch('job_runner.PIPELINE_HANDLERS')
    def test_session_management_on_error(self, mock_handlers, mock_session_local):
        """Test proper session management when job fails."""
        # Setup
        job = self.create_job_mock(1, "individual_property_fetch", {"property_id": "123"})
        
        mock_session = Mock()
        mock_session.query.return_value.order_by.return_value.first.side_effect = [job, None]
        mock_session_local.return_value = mock_session
        
        # Mock the handler to raise an exception
        mock_handler = Mock()
        mock_handler.side_effect = Exception("Test error")
        mock_handlers.get.return_value = mock_handler
        
        # Execute
        process_pipeline_jobs()
        
        # Verify session management
        mock_session_local.assert_called()   # Session was created
        mock_session.rollback.assert_called()  # Changes were rolled back
        mock_session.close.assert_called()     # Session was closed

    @patch('job_runner.SessionLocal')
    def test_session_management_on_unknown_handler(self, mock_session_local):
        """Test proper session management when job has unknown handler."""
        # Setup
        job = self.create_job_mock(1, "unknown_pipeline", {"data": "test"})
        
        mock_session = Mock()
        mock_session.query.return_value.order_by.return_value.first.side_effect = [job, None]
        mock_session_local.return_value = mock_session
        
        # Execute
        process_pipeline_jobs()
        
        # Verify session management
        mock_session_local.assert_called()  # Session was created
        mock_session.commit.assert_called()  # Changes were committed (job deleted)
        mock_session.close.assert_called()   # Session was closed

    @patch('job_runner.SessionLocal')
    @patch('job_runner.PIPELINE_HANDLERS')
    def test_mixed_success_and_failure_scenarios(self, mock_handlers, mock_session_local):
        """Test processing jobs with mixed success and failure scenarios."""
        # Setup - multiple jobs with different outcomes
        job1 = self.create_job_mock(1, "individual_property_fetch", {"property_id": "123"})  # Success
        job2 = self.create_job_mock(2, "unknown_pipeline", {"data": "test"})                # Unknown handler
        job3 = self.create_job_mock(3, "fetch_zestimate", {"property_id": "456"})           # Will fail
        
        mock_session = Mock()
        mock_session.query.return_value.order_by.return_value.first.side_effect = [job1, job2, job3, None]
        mock_session_local.return_value = mock_session
        
        # Mock handlers - first two succeed, third fails
        def mock_handler_side_effect(*args, **kwargs):
            # Check if this is the third job (fetch_zestimate with property_id 456)
            if len(args) >= 1 and isinstance(args[0], dict) and args[0].get("property_id") == "456":
                raise Exception("Test error")
            return None
        
        mock_handler = Mock()
        mock_handler.side_effect = mock_handler_side_effect
        mock_handlers.get.return_value = mock_handler
        
        # Execute
        process_pipeline_jobs()
        
        # Verify outcomes
        # Job 1: Success - deleted and committed
        # Job 2: Unknown handler - deleted and committed  
        # Job 3: Failed - not deleted, but retry info committed
        self.assertEqual(mock_session.delete.call_count, 2)  # Only first two jobs deleted
        self.assertEqual(mock_session.commit.call_count, 3)  # Two commits (for successful deletions) + 1 for retry info
        self.assertEqual(mock_session.rollback.call_count, 1)  # One rollback (for failed job before retry)
        self.assertEqual(mock_session.close.call_count, 4)  # Called 4 times (once per iteration)

    @patch('job_runner.SessionLocal')
    @patch('job_runner.PIPELINE_HANDLERS')
    def test_job_ordering(self, mock_handlers, mock_session_local):
        """Test that jobs are processed in order by ID."""
        # Setup - multiple jobs with different IDs
        job1 = self.create_job_mock(1, "individual_property_fetch", {"property_id": "123"})
        job2 = self.create_job_mock(2, "fetch_zestimate", {"property_id": "456"})
        job3 = self.create_job_mock(3, "individual_property_fetch", {"property_id": "789"})
        
        mock_session = Mock()
        mock_session.query.return_value.order_by.return_value.first.side_effect = [job1, job2, job3, None]
        mock_session_local.return_value = mock_session
        
        # Mock the handlers to succeed
        mock_handler = Mock()
        mock_handlers.get.return_value = mock_handler
        
        # Execute
        process_pipeline_jobs()
        
        # Verify jobs were processed in order
        mock_session.query.assert_called_with(Pipline_Tables)
        mock_session.query.return_value.order_by.assert_called_with(Pipline_Tables.id)
        
        # Verify all jobs were processed
        self.assertEqual(mock_session.delete.call_count, 3)

    @patch('job_runner.SessionLocal')
    @patch('job_runner.PIPELINE_HANDLERS')
    def test_empty_payload_handling(self, mock_handlers, mock_session_local):
        """Test handling of jobs with empty or None payload."""
        # Setup - job with empty payload
        job = self.create_job_mock(1, "individual_property_fetch", {})
        
        mock_session = Mock()
        mock_session.query.return_value.order_by.return_value.first.side_effect = [job, None]
        mock_session_local.return_value = mock_session
        
        # Mock the handler to succeed
        mock_handler = Mock()
        mock_handlers.get.return_value = mock_handler
        
        # Execute
        process_pipeline_jobs()
        
        # Verify job was still processed (handler should handle empty payload)
        mock_session.delete.assert_called_once_with(job)
        mock_session.commit.assert_called_once()


if __name__ == '__main__':
    unittest.main() 