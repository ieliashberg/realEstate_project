import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta
import sys
import os

# Add the project directory to the path so we can import the modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from job_runner import process_pipeline_jobs, handle_sold_or_for_sale_homes_fetch
from populate_sold_and_for_sale_queues import populate_sold_and_for_sale_queues
from job_table_helper import enqueue_job
from dataBase import Pipline_Tables, Zipcodes


class TestIntegration(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.mock_session = Mock()
        self.sample_zipcode = "12345"
        self.sample_payload = {
            "zipcode": self.sample_zipcode
        }
        
        # Sample home data
        self.sample_homes = [
            {
                'propertyId': '12345678',
                'streetLine': {'value': '123 Test St'},
                'city': 'Test City',
                'state': 'CA',
                'zip': '12345',
                'latLong': {'value': {'latitude': 37.7749, 'longitude': -122.4194}},
                'lotSize': {'value': 5000},
                'yearBuilt': {'value': 1990},
                'uiPropertyType': 'home',
                'beds': 3,
                'baths': 2,
                'sqFt': {'value': 1500},
                'stories': 2,
                'unitNumber': {'value': None},
                'hoa': {'value': 100},
                'newConstructionCommunityInfo': {'builderName': 'Test Builder'},
                'mlsStatus': 'Active',
                'url': '/test-url',
                'isNewConstruction': False,
                'price': {'value': 500000},
                'dom': {'value': 30}
            }
        ]

    @patch('job_runner.SessionLocal')
    @patch('job_runner.fetch_homes_json_from_zipcode')
    @patch('job_runner.upsert_initial_info')
    @patch('job_runner.enqueue_job')
    def test_sold_homes_fetch_integration(self, mock_enqueue_job, mock_upsert_initial_info, 
                                        mock_fetch_homes, mock_session_local):
        """Test integration of sold homes fetch pipeline."""
        # Setup
        mock_session_local.return_value = self.mock_session
        mock_fetch_homes.return_value = self.sample_homes
        mock_upsert_initial_info.return_value = {
            "property_id": 123,
            "listing_id": 456,
            "address": "123 Test St",
            "city": "Test City",
            "state": "CA",
            "zipcode": "12345",
            "redfin_property_id": "12345678",
            "isNewProperty": True
        }
        
        # Execute
        handle_sold_or_for_sale_homes_fetch("sold_homes_fetch", self.sample_payload, self.mock_session)
        
        # Verify
        mock_fetch_homes.assert_called_once_with("sold_homes_fetch", self.sample_zipcode)
        mock_upsert_initial_info.assert_called_once_with(self.mock_session, self.sample_homes[0])
        
        # Should enqueue 2 jobs per home (individual_property_fetch and fetch_zestimate)
        self.assertEqual(mock_enqueue_job.call_count, 2)
        
        # Check first enqueued job (individual_property_fetch)
        first_call = mock_enqueue_job.call_args_list[0]
        self.assertEqual(first_call[0][1], "individual_property_fetch")
        
        # Check second enqueued job (fetch_zestimate)
        second_call = mock_enqueue_job.call_args_list[1]
        self.assertEqual(second_call[0][1], "fetch_zestimate")

    @patch('job_runner.SessionLocal')
    @patch('job_runner.fetch_homes_json_from_zipcode')
    def test_sold_homes_fetch_no_homes(self, mock_fetch_homes, mock_session_local):
        """Test sold homes fetch when no homes are found."""
        # Setup
        mock_session_local.return_value = self.mock_session
        mock_fetch_homes.return_value = []
        
        # Execute
        handle_sold_or_for_sale_homes_fetch("sold_homes_fetch", self.sample_payload, self.mock_session)
        
        # Verify
        mock_fetch_homes.assert_called_once_with("sold_homes_fetch", self.sample_zipcode)

    @patch('populate_sold_and_for_sale_queues.SessionLocal')
    @patch('populate_sold_and_for_sale_queues.datetime')
    @patch('populate_sold_and_for_sale_queues.enqueue_job')
    def test_populate_queues_integration(self, mock_enqueue_job, mock_datetime, mock_session_local):
        """Test integration of populate_sold_and_for_sale_queues."""
        # Setup
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = now
        
        mock_session = Mock()
        mock_session_local.return_value = mock_session
        
        # Create mock zipcode that needs both jobs
        mock_zipcode = Mock(spec=Zipcodes)
        mock_zipcode.zipcode = "12345"
        mock_zipcode.for_sale_fetch_frequency = timedelta(hours=6)
        mock_zipcode.sold_fetch_frequency = timedelta(hours=12)
        mock_zipcode.last_for_sale_fetch = now - timedelta(hours=7)  # Due
        mock_zipcode.last_sold_fetch = now - timedelta(hours=13)     # Due
        
        mock_session.query.return_value.all.return_value = [mock_zipcode]
        
        # Execute
        populate_sold_and_for_sale_queues()
        
        # Verify
        self.assertEqual(mock_enqueue_job.call_count, 2)
        
        # Check first enqueued job (for_sale_homes_fetch)
        first_call = mock_enqueue_job.call_args_list[0]
        self.assertEqual(first_call[0][1], "for_sale_homes_fetch")
        
        # Check second enqueued job (sold_homes_fetch)
        second_call = mock_enqueue_job.call_args_list[1]
        self.assertEqual(second_call[0][1], "sold_homes_fetch")

    @patch('job_runner.SessionLocal')
    def test_process_single_job_no_jobs(self, mock_session_local):
        """Test process_single_job when no jobs are in queue."""
        # Setup
        mock_session = Mock()
        mock_session.query.return_value.order_by.return_value.first.return_value = None
        mock_session_local.return_value = mock_session
        
        # Execute
        result = process_single_job()
        
        # Verify
        self.assertFalse(result)
        mock_session.query.assert_called_once_with(Pipline_Tables)
        mock_session.close.assert_called_once()

    @patch('job_runner.SessionLocal')
    def test_process_single_job_unknown_handler(self, mock_session_local):
        """Test process_single_job with unknown pipeline handler."""
        # Setup
        mock_session = Mock()
        mock_job = Mock(spec=Pipline_Tables)
        mock_job.id = 1
        mock_job.name_of_pipeline = "unknown_pipeline"
        mock_job.payload = {"test": "data"}
        
        mock_session.query.return_value.order_by.return_value.first.return_value = mock_job
        mock_session_local.return_value = mock_session
        
        # Execute
        result = process_single_job()
        
        # Verify
        self.assertTrue(result)
        mock_session.delete.assert_called_once_with(mock_job)
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    @patch('job_runner.SessionLocal')
    def test_process_single_job_max_retries_exceeded(self, mock_session_local):
        """Test process_single_job when job exceeds max retries."""
        # Setup
        mock_session = Mock()
        mock_job = Mock(spec=Pipline_Tables)
        mock_job.id = 1
        mock_job.name_of_pipeline = "individual_property_fetch"
        mock_job.payload = {"_retry_count": 3, "property_id": 123}  # Exceeds MAX_RETRIES (3)
        
        mock_session.query.return_value.order_by.return_value.first.return_value = mock_job
        mock_session_local.return_value = mock_session
        
        # Execute
        result = process_single_job()
        
        # Verify
        self.assertTrue(result)
        mock_session.delete.assert_called_once_with(mock_job)
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    @patch('job_runner.SessionLocal')
    def test_process_single_job_successful_execution(self, mock_session_local):
        """Test process_single_job with successful job execution."""
        # Setup
        mock_session = Mock()
        mock_job = Mock(spec=Pipline_Tables)
        mock_job.id = 1
        mock_job.name_of_pipeline = "individual_property_fetch"
        mock_job.payload = {"property_id": 123}
        
        mock_session.query.return_value.order_by.return_value.first.return_value = mock_job
        mock_session_local.return_value = mock_session
        
        # Mock the handlers
        mock_handler = Mock()
        mock_handler.return_value = None
        
        with patch('job_runner.PIPELINE_HANDLERS', {'individual_property_fetch': mock_handler}):
            # Execute
            result = process_single_job()
            
            # Verify
            self.assertTrue(result)
            mock_handler.assert_called_once_with({"property_id": 123})
            mock_session.delete.assert_called_once_with(mock_job)
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()

    @patch('job_runner.SessionLocal')
    def test_process_single_job_job_failure_retry(self, mock_session_local):
        """Test process_single_job with job failure and retry."""
        # Setup
        mock_session = Mock()
        mock_job = Mock(spec=Pipline_Tables)
        mock_job.id = 1
        mock_job.name_of_pipeline = "individual_property_fetch"
        mock_job.payload = {"property_id": 123}
        
        mock_session.query.return_value.order_by.return_value.first.return_value = mock_job
        mock_session_local.return_value = mock_session
        
        # Mock the handlers
        mock_handler = Mock()
        mock_handler.side_effect = Exception("Test error")
        
        with patch('job_runner.PIPELINE_HANDLERS', {'individual_property_fetch': mock_handler}):
            # Execute
            result = process_single_job()
            
            # Verify
            self.assertTrue(result)
            # The handler is called with the updated payload (including retry info)
            expected_payload = {"property_id": 123, "_retry_count": 1, "_last_error": "Test error", "_last_error_at": mock_job.payload["_last_error_at"], "_next_retry_at": mock_job.payload["_next_retry_at"]}
            mock_handler.assert_called_once_with(expected_payload)
            
            # Should update retry information in payload
            self.assertEqual(mock_job.payload["_retry_count"], 1)
            self.assertIn("_last_error", mock_job.payload)
            self.assertIn("_last_error_at", mock_job.payload)
            self.assertIn("_next_retry_at", mock_job.payload)
            
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()

    @patch('job_runner.SessionLocal')
    def test_process_single_job_with_provided_session(self, mock_session_local):
        """Test process_single_job with a provided session (should not close it)."""
        # Setup
        mock_session = Mock()
        mock_job = Mock(spec=Pipline_Tables)
        mock_job.id = 1
        mock_job.name_of_pipeline = "individual_property_fetch"
        mock_job.payload = {"property_id": 123}
        
        mock_session.query.return_value.order_by.return_value.first.return_value = mock_job
        
        # Mock the handlers
        mock_handler = Mock()
        mock_handler.return_value = None
        
        with patch('job_runner.PIPELINE_HANDLERS', {'individual_property_fetch': mock_handler}):
            # Execute with provided session
            result = process_single_job(mock_session)
            
            # Verify
            self.assertTrue(result)
            mock_session_local.assert_not_called()  # Should not create new session
            mock_session.close.assert_not_called()  # Should not close provided session
            mock_handler.assert_called_once_with({"property_id": 123})
            mock_session.delete.assert_called_once_with(mock_job)
            mock_session.commit.assert_called_once()


if __name__ == '__main__':
    unittest.main()
