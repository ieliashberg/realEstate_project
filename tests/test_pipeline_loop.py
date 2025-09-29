import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
import sys
import os
import signal
import time

# Add the project directory to the path so we can import the modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.pipeline.runner import process_pipeline_jobs


class TimeoutException(Exception):
    """Exception raised when a test times out."""
    pass


def timeout_handler(signum, frame):
    """Signal handler for timeout."""
    raise TimeoutException("Test timed out")


class TestPipelineLoop(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Set up timeout handler
        signal.signal(signal.SIGALRM, timeout_handler)
    
    def tearDown(self):
        """Clean up after each test method."""
        # Cancel any pending alarm
        signal.alarm(0)

    @patch('job_runner.process_single_job')
    def test_process_pipeline_jobs_no_jobs_immediate_exit(self, mock_process_single_job):
        """Test that process_pipeline_jobs exits immediately when no jobs are available."""
        # Setup
        mock_process_single_job.return_value = False  # No jobs available
        
        # Set a 5-second timeout to ensure the function exits quickly
        signal.alarm(5)
        
        try:
            # Execute
            process_pipeline_jobs()
            
            # Verify
            mock_process_single_job.assert_called_once()
            
        except TimeoutException:
            self.fail("process_pipeline_jobs did not exit when no jobs were available")
        finally:
            signal.alarm(0)

    @patch('job_runner.process_single_job')
    def test_process_pipeline_jobs_processes_multiple_jobs(self, mock_process_single_job):
        """Test that process_pipeline_jobs processes multiple jobs then exits."""
        # Setup - simulate 3 jobs then no more jobs
        mock_process_single_job.side_effect = [True, True, True, False]
        
        # Set a 5-second timeout
        signal.alarm(5)
        
        try:
            # Execute
            process_pipeline_jobs()
            
            # Verify - should have been called 4 times (3 jobs + 1 to find no more jobs)
            self.assertEqual(mock_process_single_job.call_count, 4)
            
        except TimeoutException:
            self.fail("process_pipeline_jobs did not exit after processing jobs")
        finally:
            signal.alarm(0)

    @patch('job_runner.process_single_job')
    def test_process_pipeline_jobs_infinite_loop_protection(self, mock_process_single_job):
        """Test that process_pipeline_jobs doesn't run infinitely if process_single_job keeps returning True."""
        # Setup - simulate infinite jobs (this should not happen in real usage)
        mock_process_single_job.return_value = True
        
        # Set a 2-second timeout to catch infinite loops
        signal.alarm(2)
        
        try:
            # Execute - this should timeout due to infinite loop
            process_pipeline_jobs()
            
            # If we get here, the function exited unexpectedly
            self.fail("process_pipeline_jobs should have run infinitely with infinite jobs")
            
        except TimeoutException:
            # This is expected - the function should timeout due to infinite loop
            # Verify that process_single_job was called many times
            self.assertGreater(mock_process_single_job.call_count, 10)
        finally:
            signal.alarm(0)


if __name__ == '__main__':
    unittest.main()
