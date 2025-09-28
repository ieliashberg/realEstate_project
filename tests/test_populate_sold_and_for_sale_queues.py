import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta, timezone
import sys
import os

# Add the project directory to the path so we can import the modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from populate_sold_and_for_sale_queues import populate_sold_and_for_sale_queues
from dataBase import Zipcodes


class TestPopulateSoldAndForSaleQueues(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.mock_session = Mock()
        self.mock_zipcode = Mock(spec=Zipcodes)
        self.mock_zipcode.zipcode = "12345"
        self.mock_zipcode.for_sale_fetch_frequency = timedelta(hours=6)
        self.mock_zipcode.sold_fetch_frequency = timedelta(hours=12)
        
    def create_zipcode_mock(self, zipcode, for_sale_freq, sold_freq, 
                           last_for_sale_fetch=None, last_sold_fetch=None):
        """Helper method to create a zipcode mock with specified attributes."""
        mock_zip = Mock(spec=Zipcodes)
        mock_zip.zipcode = zipcode
        mock_zip.for_sale_fetch_frequency = for_sale_freq
        mock_zip.sold_fetch_frequency = sold_freq
        mock_zip.last_for_sale_fetch = last_for_sale_fetch
        mock_zip.last_sold_fetch = last_sold_fetch
        return mock_zip

    @patch('populate_sold_and_for_sale_queues.SessionLocal')
    @patch('populate_sold_and_for_sale_queues.datetime')
    @patch('populate_sold_and_for_sale_queues.enqueue_job')
    def test_both_jobs_enqueued_when_due(self, mock_enqueue_job, mock_datetime, mock_session_local):
        """Test that both for-sale and sold jobs are enqueued when both are due."""
        # Setup
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = now
        
        # Create zipcode that needs both jobs
        zipcode = self.create_zipcode_mock(
            zipcode="12345",
            for_sale_freq=timedelta(hours=6),
            sold_freq=timedelta(hours=12),
            last_for_sale_fetch=now - timedelta(hours=7),  # Due
            last_sold_fetch=now - timedelta(hours=13)      # Due
        )
        
        mock_session = Mock()
        mock_session.query.return_value.all.return_value = [zipcode]
        mock_session_local.return_value = mock_session
        
        # Execute
        populate_sold_and_for_sale_queues()
        
        # Verify
        self.assertEqual(mock_enqueue_job.call_count, 2)
        
        # Check for-sale job
        for_sale_call = mock_enqueue_job.call_args_list[0]
        self.assertEqual(for_sale_call[0][1], "for_sale_homes_fetch")
        self.assertEqual(for_sale_call[0][2], {"zipcode": "12345"})
        
        # Check sold job
        sold_call = mock_enqueue_job.call_args_list[1]
        self.assertEqual(sold_call[0][1], "sold_homes_fetch")
        self.assertEqual(sold_call[0][2], {"zipcode": "12345"})
        
        # Verify timestamps were updated
        self.assertEqual(zipcode.last_for_sale_fetch, now)
        self.assertEqual(zipcode.last_sold_fetch, now)
        
        # Verify session was committed and closed
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    @patch('populate_sold_and_for_sale_queues.SessionLocal')
    @patch('populate_sold_and_for_sale_queues.datetime')
    @patch('populate_sold_and_for_sale_queues.enqueue_job')
    def test_no_jobs_enqueued_when_not_due(self, mock_enqueue_job, mock_datetime, mock_session_local):
        """Test that no jobs are enqueued when neither is due."""
        # Setup
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = now
        
        # Create zipcode that doesn't need any jobs
        zipcode = self.create_zipcode_mock(
            zipcode="12345",
            for_sale_freq=timedelta(hours=6),
            sold_freq=timedelta(hours=12),
            last_for_sale_fetch=now - timedelta(hours=5),  # Not due
            last_sold_fetch=now - timedelta(hours=11)      # Not due
        )
        
        mock_session = Mock()
        mock_session.query.return_value.all.return_value = [zipcode]
        mock_session_local.return_value = mock_session
        
        # Execute
        populate_sold_and_for_sale_queues()
        
        # Verify
        mock_enqueue_job.assert_not_called()
        
        # Verify timestamps were not updated
        self.assertNotEqual(zipcode.last_for_sale_fetch, now)
        self.assertNotEqual(zipcode.last_sold_fetch, now)
        
        # Verify session was committed and closed
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    @patch('populate_sold_and_for_sale_queues.SessionLocal')
    @patch('populate_sold_and_for_sale_queues.datetime')
    @patch('populate_sold_and_for_sale_queues.enqueue_job')
    def test_only_for_sale_job_enqueued(self, mock_enqueue_job, mock_datetime, mock_session_local):
        """Test that only for-sale job is enqueued when only that one is due."""
        # Setup
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = now
        
        # Create zipcode that only needs for-sale job
        zipcode = self.create_zipcode_mock(
            zipcode="12345",
            for_sale_freq=timedelta(hours=6),
            sold_freq=timedelta(hours=12),
            last_for_sale_fetch=now - timedelta(hours=7),  # Due
            last_sold_fetch=now - timedelta(hours=11)      # Not due
        )
        
        mock_session = Mock()
        mock_session.query.return_value.all.return_value = [zipcode]
        mock_session_local.return_value = mock_session
        
        # Execute
        populate_sold_and_for_sale_queues()
        
        # Verify
        mock_enqueue_job.assert_called_once()
        call = mock_enqueue_job.call_args_list[0]
        self.assertEqual(call[0][1], "for_sale_homes_fetch")
        self.assertEqual(call[0][2], {"zipcode": "12345"})
        
        # Verify only for-sale timestamp was updated
        self.assertEqual(zipcode.last_for_sale_fetch, now)
        self.assertNotEqual(zipcode.last_sold_fetch, now)

    @patch('populate_sold_and_for_sale_queues.SessionLocal')
    @patch('populate_sold_and_for_sale_queues.datetime')
    @patch('populate_sold_and_for_sale_queues.enqueue_job')
    def test_only_sold_job_enqueued(self, mock_enqueue_job, mock_datetime, mock_session_local):
        """Test that only sold job is enqueued when only that one is due."""
        # Setup
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = now
        
        # Create zipcode that only needs sold job
        zipcode = self.create_zipcode_mock(
            zipcode="12345",
            for_sale_freq=timedelta(hours=6),
            sold_freq=timedelta(hours=12),
            last_for_sale_fetch=now - timedelta(hours=5),  # Not due
            last_sold_fetch=now - timedelta(hours=13)      # Due
        )
        
        mock_session = Mock()
        mock_session.query.return_value.all.return_value = [zipcode]
        mock_session_local.return_value = mock_session
        
        # Execute
        populate_sold_and_for_sale_queues()
        
        # Verify
        mock_enqueue_job.assert_called_once()
        call = mock_enqueue_job.call_args_list[0]
        self.assertEqual(call[0][1], "sold_homes_fetch")
        self.assertEqual(call[0][2], {"zipcode": "12345"})
        
        # Verify only sold timestamp was updated
        self.assertNotEqual(zipcode.last_for_sale_fetch, now)
        self.assertEqual(zipcode.last_sold_fetch, now)

    @patch('populate_sold_and_for_sale_queues.SessionLocal')
    @patch('populate_sold_and_for_sale_queues.datetime')
    @patch('populate_sold_and_for_sale_queues.enqueue_job')
    def test_multiple_zipcodes(self, mock_enqueue_job, mock_datetime, mock_session_local):
        """Test handling of multiple zipcodes with different due states."""
        # Setup
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = now
        
        # Create multiple zipcodes
        zipcode1 = self.create_zipcode_mock(
            zipcode="12345",
            for_sale_freq=timedelta(hours=6),
            sold_freq=timedelta(hours=12),
            last_for_sale_fetch=now - timedelta(hours=7),  # Due
            last_sold_fetch=now - timedelta(hours=5)       # Not due
        )
        
        zipcode2 = self.create_zipcode_mock(
            zipcode="67890",
            for_sale_freq=timedelta(hours=6),
            sold_freq=timedelta(hours=12),
            last_for_sale_fetch=now - timedelta(hours=5),  # Not due
            last_sold_fetch=now - timedelta(hours=13)      # Due
        )
        
        zipcode3 = self.create_zipcode_mock(
            zipcode="11111",
            for_sale_freq=timedelta(hours=6),
            sold_freq=timedelta(hours=12),
            last_for_sale_fetch=now - timedelta(hours=7),  # Due
            last_sold_fetch=now - timedelta(hours=13)      # Due
        )
        
        mock_session = Mock()
        mock_session.query.return_value.all.return_value = [zipcode1, zipcode2, zipcode3]
        mock_session_local.return_value = mock_session
        
        # Execute
        populate_sold_and_for_sale_queues()
        
        # Verify
        self.assertEqual(mock_enqueue_job.call_count, 4)  # 1 + 1 + 2
        
        # Check calls were made for the right zipcodes
        zipcodes_called = [call[0][2]["zipcode"] for call in mock_enqueue_job.call_args_list]
        self.assertIn("12345", zipcodes_called)
        self.assertIn("67890", zipcodes_called)
        self.assertIn("11111", zipcodes_called)
        self.assertEqual(zipcodes_called.count("11111"), 2)  # Both jobs for this zipcode

    @patch('populate_sold_and_for_sale_queues.SessionLocal')
    @patch('populate_sold_and_for_sale_queues.datetime')
    @patch('populate_sold_and_for_sale_queues.enqueue_job')
    def test_null_last_fetch_timestamps(self, mock_enqueue_job, mock_datetime, mock_session_local):
        """Test handling of null last fetch timestamps (first time running)."""
        # Setup
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = now
        mock_datetime.fromtimestamp.return_value = datetime(1970, 1, 1, tzinfo=timezone.utc)
        
        # Create zipcode with null timestamps
        zipcode = self.create_zipcode_mock(
            zipcode="12345",
            for_sale_freq=timedelta(hours=6),
            sold_freq=timedelta(hours=12),
            last_for_sale_fetch=None,
            last_sold_fetch=None
        )
        
        mock_session = Mock()
        mock_session.query.return_value.all.return_value = [zipcode]
        mock_session_local.return_value = mock_session
        
        # Execute
        populate_sold_and_for_sale_queues()
        
        # Verify both jobs are enqueued (since epoch time + frequency < now)
        self.assertEqual(mock_enqueue_job.call_count, 2)
        
        # Verify timestamps were updated
        self.assertEqual(zipcode.last_for_sale_fetch, now)
        self.assertEqual(zipcode.last_sold_fetch, now)

    @patch('populate_sold_and_for_sale_queues.SessionLocal')
    @patch('populate_sold_and_for_sale_queues.datetime')
    @patch('populate_sold_and_for_sale_queues.enqueue_job')
    def test_exact_due_time(self, mock_enqueue_job, mock_datetime, mock_session_local):
        """Test that jobs are enqueued when exactly due (not just overdue)."""
        # Setup
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = now
        
        # Create zipcode that is exactly due
        zipcode = self.create_zipcode_mock(
            zipcode="12345",
            for_sale_freq=timedelta(hours=6),
            sold_freq=timedelta(hours=12),
            last_for_sale_fetch=now - timedelta(hours=6),  # Exactly due
            last_sold_fetch=now - timedelta(hours=12)      # Exactly due
        )
        
        mock_session = Mock()
        mock_session.query.return_value.all.return_value = [zipcode]
        mock_session_local.return_value = mock_session
        
        # Execute
        populate_sold_and_for_sale_queues()
        
        # Verify both jobs are enqueued
        self.assertEqual(mock_enqueue_job.call_count, 2)

    @patch('populate_sold_and_for_sale_queues.SessionLocal')
    @patch('populate_sold_and_for_sale_queues.datetime')
    @patch('populate_sold_and_for_sale_queues.enqueue_job')
    def test_error_handling_and_rollback(self, mock_enqueue_job, mock_datetime, mock_session_local):
        """Test error handling and session rollback when an exception occurs."""
        # Setup
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = now
        
        # Make enqueue_job raise an exception
        mock_enqueue_job.side_effect = Exception("Database error")
        
        zipcode = self.create_zipcode_mock(
            zipcode="12345",
            for_sale_freq=timedelta(hours=6),
            sold_freq=timedelta(hours=12),
            last_for_sale_fetch=now - timedelta(hours=7),  # Due
            last_sold_fetch=now - timedelta(hours=5)       # Not due
        )
        
        mock_session = Mock()
        mock_session.query.return_value.all.return_value = [zipcode]
        mock_session_local.return_value = mock_session
        
        # Execute and verify exception is raised
        with self.assertRaises(Exception):
            populate_sold_and_for_sale_queues()
        
        # Verify rollback was called
        mock_session.rollback.assert_called_once()
        
        # Verify session was still closed
        mock_session.close.assert_called_once()
        
        # Verify commit was not called
        mock_session.commit.assert_not_called()

    @patch('populate_sold_and_for_sale_queues.SessionLocal')
    @patch('populate_sold_and_for_sale_queues.datetime')
    @patch('populate_sold_and_for_sale_queues.enqueue_job')
    def test_session_always_closed(self, mock_enqueue_job, mock_datetime, mock_session_local):
        """Test that session is always closed, even if an exception occurs."""
        # Setup
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = now
        
        # Make session.query raise an exception
        mock_session = Mock()
        mock_session.query.side_effect = Exception("Query error")
        mock_session_local.return_value = mock_session
        
        # Execute and verify exception is raised
        with self.assertRaises(Exception):
            populate_sold_and_for_sale_queues()
        
        # Verify session was still closed
        mock_session.close.assert_called_once()

    @patch('populate_sold_and_for_sale_queues.SessionLocal')
    @patch('populate_sold_and_for_sale_queues.datetime')
    @patch('populate_sold_and_for_sale_queues.enqueue_job')
    def test_empty_zipcodes_list(self, mock_enqueue_job, mock_datetime, mock_session_local):
        """Test behavior when no zipcodes are found in the database."""
        # Setup
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = now
        
        mock_session = Mock()
        mock_session.query.return_value.all.return_value = []
        mock_session_local.return_value = mock_session
        
        # Execute
        populate_sold_and_for_sale_queues()
        
        # Verify no jobs were enqueued
        mock_enqueue_job.assert_not_called()
        
        # Verify session was committed and closed
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()


if __name__ == '__main__':
    unittest.main() 