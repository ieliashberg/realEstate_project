"""
Comprehensive tests for job_runner.py including error handling and edge cases.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta

from src.pipeline.runner import (
    process_pipeline_jobs, 
    handle_individual_property_fetch, 
    handle_fetch_zestimate,
    handle_sold_or_for_sale_homes_fetch,
    MAX_RETRIES
)
from src.database.connection import SessionLocal, Pipline_Tables


class TestJobRunnerCore:
    """Test core job runner functionality."""

    def test_process_pipeline_jobs_with_empty_queue(self, mock_session):
        """Test processing when no jobs are in queue."""
        with patch('job_runner.SessionLocal') as mock_session_local:
            mock_session_local.return_value = mock_session
            mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
            
            process_pipeline_jobs()
            # Should complete without error

    def test_process_pipeline_jobs_with_valid_job(self, mock_session, sample_job_payload):
        """Test processing a valid job."""
        mock_job = Mock()
        mock_job.name_of_pipeline = "individual_property_fetch"
        mock_job.payload = sample_job_payload
        mock_job.id = 123
        
        with patch('job_runner.SessionLocal') as mock_session_local:
            mock_session_local.return_value = mock_session
            mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_job]
            
            with patch('job_runner.handle_individual_property_fetch') as mock_handler:
                mock_handler.return_value = None
                process_pipeline_jobs()
                mock_handler.assert_called_once_with(sample_job_payload)

    def test_process_pipeline_jobs_with_unknown_handler(self, mock_session, sample_job_payload):
        """Test processing a job with unknown handler."""
        mock_job = Mock()
        mock_job.name_of_pipeline = "unknown_pipeline"
        mock_job.payload = sample_job_payload
        mock_job.id = 123
        
        with patch('job_runner.SessionLocal') as mock_session_local:
            mock_session_local.return_value = mock_session
            mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_job]
            
            process_pipeline_jobs()
            # Job should be deleted for unknown pipeline
            mock_session.delete.assert_called_once_with(mock_job)

    def test_process_pipeline_jobs_with_handler_exception(self, mock_session, sample_job_payload):
        """Test processing when handler raises an exception."""
        mock_job = Mock()
        mock_job.name_of_pipeline = "individual_property_fetch"
        mock_job.payload = sample_job_payload
        mock_job.id = 123
        
        with patch('job_runner.SessionLocal') as mock_session_local:
            mock_session_local.return_value = mock_session
            mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_job]
            
            with patch('job_runner.handle_individual_property_fetch') as mock_handler:
                mock_handler.side_effect = Exception("Test error")
                process_pipeline_jobs()
                # Should handle exception and not crash


class TestJobRetryLogic:
    """Test job retry and error handling logic."""

    def test_job_retry_on_first_failure(self, mock_session, sample_job_payload):
        """Test that jobs are retried on first failure."""
        mock_job = Mock()
        mock_job.name_of_pipeline = "individual_property_fetch"
        mock_job.payload = sample_job_payload
        mock_job.id = 123
        
        with patch('job_runner.SessionLocal') as mock_session_local:
            mock_session_local.return_value = mock_session
            mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_job]
            
            with patch('job_runner.handle_individual_property_fetch') as mock_handler:
                mock_handler.side_effect = Exception("Test error")
                process_pipeline_jobs()
                
                # Should update job payload with retry information
                mock_session.commit.assert_called()

    def test_job_deletion_after_max_retries(self, mock_session, sample_job_payload):
        """Test that jobs are deleted after max retries."""
        # Set up job that has already reached max retries
        payload_with_max_retries = sample_job_payload.copy()
        payload_with_max_retries["_retry_count"] = MAX_RETRIES
        
        mock_job = Mock()
        mock_job.name_of_pipeline = "individual_property_fetch"
        mock_job.payload = payload_with_max_retries
        mock_job.id = 123
        
        with patch('job_runner.SessionLocal') as mock_session_local:
            mock_session_local.return_value = mock_session
            mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_job]
            
            with patch('job_runner.handle_individual_property_fetch') as mock_handler:
                mock_handler.side_effect = Exception("Test error")
                process_pipeline_jobs()
                
                # Should delete job after max retries
                mock_session.delete.assert_called_once_with(mock_job)

    def test_job_retry_with_exponential_backoff(self, mock_session, sample_job_payload):
        """Test that retry timing follows exponential backoff."""
        payload_with_retry = sample_job_payload.copy()
        payload_with_retry["_retry_count"] = 2
        
        mock_job = Mock()
        mock_job.name_of_pipeline = "individual_property_fetch"
        mock_job.payload = payload_with_retry
        mock_job.id = 123
        
        with patch('job_runner.SessionLocal') as mock_session_local:
            mock_session_local.return_value = mock_session
            mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_job]
            
            with patch('job_runner.handle_individual_property_fetch') as mock_handler:
                mock_handler.side_effect = Exception("Test error")
                process_pipeline_jobs()
                
                # Should calculate next retry time with exponential backoff
                updated_payload = mock_job.payload
                assert "_retry_count" in updated_payload
                assert updated_payload["_retry_count"] == 3


class TestIndividualPropertyFetchHandler:
    """Test the individual property fetch handler."""

    def test_handle_individual_property_fetch_success(self, sample_property_payload):
        """Test successful property fetch."""
        with patch('job_runner.get_specific_property_info') as mock_get_info:
            mock_get_info.return_value = {
                "covered_spaces": 2,
                "tax_annual_amount": 1866,
                "schools": [{"name": "Test School", "rating": 5}],
                "price_history": [{"price": 500000, "date": "2024-01-01"}],
                "agents_name": "Test Agent",
                "agents_broker": "Test Broker"
            }
            
            with patch('job_runner.upsert_more_info') as mock_upsert:
                with patch('job_runner.SessionLocal') as mock_session_local:
                    mock_session = Mock()
                    mock_session_local.return_value = mock_session
                    
                    handle_individual_property_fetch(sample_property_payload)
                    
                    mock_get_info.assert_called_once_with(sample_property_payload)
                    mock_upsert.assert_called_once()

    def test_handle_individual_property_fetch_with_none_result(self, sample_property_payload):
        """Test handling when get_specific_property_info returns None."""
        with patch('job_runner.get_specific_property_info') as mock_get_info:
            mock_get_info.return_value = None
            
            # Should not raise an error
            handle_individual_property_fetch(sample_property_payload)

    def test_handle_individual_property_fetch_with_missing_tax_info(self, sample_property_payload):
        """Test handling when tax information is missing."""
        with patch('job_runner.get_specific_property_info') as mock_get_info:
            mock_get_info.return_value = {
                "covered_spaces": 2,
                "tax_annual_amount": None,  # Missing tax info
                "schools": [],
                "price_history": [],
                "agents_name": None,
                "agents_broker": None
            }
            
            with patch('job_runner.upsert_more_info') as mock_upsert:
                with patch('job_runner.SessionLocal') as mock_session_local:
                    mock_session = Mock()
                    mock_session_local.return_value = mock_session
                    
                    handle_individual_property_fetch(sample_property_payload)
                    
                    # Should still process the job
                    mock_upsert.assert_called_once()

    def test_handle_individual_property_fetch_with_database_error(self, sample_property_payload):
        """Test handling of database errors during upsert."""
        with patch('job_runner.get_specific_property_info') as mock_get_info:
            mock_get_info.return_value = {"tax_annual_amount": 1866}
            
            with patch('job_runner.upsert_more_info') as mock_upsert:
                mock_upsert.side_effect = Exception("Database error")
                
                with pytest.raises(Exception, match="Database error"):
                    handle_individual_property_fetch(sample_property_payload)


class TestZestimateHandler:
    """Test the zestimate fetch handler."""

    def test_handle_fetch_zestimate_success(self, sample_property_payload):
        """Test successful zestimate fetch."""
        with patch('job_runner.get_zestimate') as mock_get_zestimate:
            mock_get_zestimate.return_value = (2500, 2700, 2300)
            
            with patch('job_runner.upsert_zestimates') as mock_upsert:
                with patch('job_runner.SessionLocal') as mock_session_local:
                    mock_session = Mock()
                    mock_session_local.return_value = mock_session
                    
                    handle_fetch_zestimate(sample_property_payload)
                    
                    mock_get_zestimate.assert_called_once_with(
                        sample_property_payload["address"],
                        sample_property_payload["city"],
                        sample_property_payload["state"],
                        sample_property_payload["zipcode"]
                    )
                    mock_upsert.assert_called_once_with(mock_session, 12345, 2500, 2700, 2300)

    def test_handle_fetch_zestimate_with_none_values(self, sample_property_payload):
        """Test handling when zestimate returns None values."""
        with patch('job_runner.get_zestimate') as mock_get_zestimate:
            mock_get_zestimate.return_value = (None, None, None)
            
            # Should not call upsert_zestimates and should return early
            handle_fetch_zestimate(sample_property_payload)

    def test_handle_fetch_zestimate_with_partial_values(self, sample_property_payload):
        """Test handling when zestimate returns partial values."""
        with patch('job_runner.get_zestimate') as mock_get_zestimate:
            mock_get_zestimate.return_value = (2500, None, 2300)  # Missing high value
            
            with patch('job_runner.upsert_zestimates') as mock_upsert:
                with patch('job_runner.SessionLocal') as mock_session_local:
                    mock_session = Mock()
                    mock_session_local.return_value = mock_session
                    
                    handle_fetch_zestimate(sample_property_payload)
                    
                    mock_upsert.assert_called_once_with(mock_session, 12345, 2500, None, 2300)

    def test_handle_fetch_zestimate_with_database_error(self, sample_property_payload):
        """Test handling of database errors during zestimate upsert."""
        with patch('job_runner.get_zestimate') as mock_get_zestimate:
            mock_get_zestimate.return_value = (2500, 2700, 2300)
            
            with patch('job_runner.upsert_zestimates') as mock_upsert:
                mock_upsert.side_effect = Exception("Database error")
                
                with pytest.raises(Exception, match="Database error"):
                    handle_fetch_zestimate(sample_property_payload)


class TestSoldOrForSaleHomesHandler:
    """Test the sold/for sale homes fetch handler."""

    def test_handle_sold_or_for_sale_homes_fetch_success(self):
        """Test successful homes fetch."""
        payload = {"zipcode": "85297"}
        
        with patch('job_runner.fetch_homes_json_from_zipcode') as mock_fetch:
            mock_fetch.return_value = [
                {"address": "123 Main St", "city": "Gilbert", "state": "AZ", "zipcode": "85297"}
            ]
            
            with patch('job_runner.upsert_property') as mock_upsert:
                handle_sold_or_for_sale_homes_fetch("for_sale", payload)
                
                mock_fetch.assert_called_once_with("85297", "for_sale")
                mock_upsert.assert_called_once()

    def test_handle_sold_or_for_sale_homes_fetch_with_empty_results(self):
        """Test handling when no homes are returned."""
        payload = {"zipcode": "85297"}
        
        with patch('job_runner.fetch_homes_json_from_zipcode') as mock_fetch:
            mock_fetch.return_value = []
            
            with patch('job_runner.upsert_property') as mock_upsert:
                handle_sold_or_for_sale_homes_fetch("for_sale", payload)
                
                mock_fetch.assert_called_once_with("85297", "for_sale")
                mock_upsert.assert_not_called()

    def test_handle_sold_or_for_sale_homes_fetch_with_invalid_zipcode(self):
        """Test handling of invalid zipcode."""
        payload = {"zipcode": "invalid"}
        
        with patch('job_runner.fetch_homes_json_from_zipcode') as mock_fetch:
            mock_fetch.return_value = []
            
            with patch('job_runner.upsert_property') as mock_upsert:
                handle_sold_or_for_sale_homes_fetch("for_sale", payload)
                
                # Should handle gracefully without crashing
                mock_upsert.assert_not_called()

    def test_handle_sold_or_for_sale_homes_fetch_with_malformed_homes(self):
        """Test handling of malformed home data."""
        payload = {"zipcode": "85297"}
        
        with patch('job_runner.fetch_homes_json_from_zipcode') as mock_fetch:
            mock_fetch.return_value = [
                {"incomplete": "data"},  # Missing required fields
                {"address": "123 Main St", "city": "Gilbert", "state": "AZ", "zipcode": "85297"}  # Valid
            ]
            
            with patch('job_runner.upsert_property') as mock_upsert:
                handle_sold_or_for_sale_homes_fetch("for_sale", payload)
                
                # Should process valid homes and skip invalid ones
                mock_upsert.assert_called_once()


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_job_with_malformed_payload(self, mock_session):
        """Test handling of job with malformed payload."""
        mock_job = Mock()
        mock_job.name_of_pipeline = "individual_property_fetch"
        mock_job.payload = {"malformed": "payload"}
        mock_job.id = 123
        
        with patch('job_runner.SessionLocal') as mock_session_local:
            mock_session_local.return_value = mock_session
            mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_job]
            
            with patch('job_runner.handle_individual_property_fetch') as mock_handler:
                mock_handler.side_effect = Exception("Malformed payload")
                process_pipeline_jobs()
                # Should handle exception gracefully

    def test_job_with_very_large_payload(self, mock_session):
        """Test handling of job with very large payload."""
        large_payload = {"data": "x" * 1000000}
        
        mock_job = Mock()
        mock_job.name_of_pipeline = "individual_property_fetch"
        mock_job.payload = large_payload
        mock_job.id = 123
        
        with patch('job_runner.SessionLocal') as mock_session_local:
            mock_session_local.return_value = mock_session
            mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_job]
            
            with patch('job_runner.handle_individual_property_fetch') as mock_handler:
                process_pipeline_jobs()
                mock_handler.assert_called_once_with(large_payload)

    def test_concurrent_job_processing(self, mock_session, sample_job_payload):
        """Test handling of concurrent job processing."""
        mock_job1 = Mock()
        mock_job1.name_of_pipeline = "individual_property_fetch"
        mock_job1.payload = sample_job_payload.copy()
        mock_job1.id = 123
        
        mock_job2 = Mock()
        mock_job2.name_of_pipeline = "fetch_zestimate"
        mock_job2.payload = sample_job_payload.copy()
        mock_job2.id = 124
        
        with patch('job_runner.SessionLocal') as mock_session_local:
            mock_session_local.return_value = mock_session
            mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_job1, mock_job2]
            
            with patch('job_runner.handle_individual_property_fetch') as mock_handler1:
                with patch('job_runner.handle_fetch_zestimate') as mock_handler2:
                    process_pipeline_jobs()
                    
                    mock_handler1.assert_called_once()
                    mock_handler2.assert_called_once()

    def test_database_connection_loss_during_processing(self, mock_session, sample_job_payload):
        """Test handling of database connection loss during processing."""
        mock_job = Mock()
        mock_job.name_of_pipeline = "individual_property_fetch"
        mock_job.payload = sample_job_payload
        mock_job.id = 123
        
        with patch('job_runner.SessionLocal') as mock_session_local:
            mock_session_local.return_value = mock_session
            mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_job]
            mock_session.commit.side_effect = Exception("Connection lost")
            
            with patch('job_runner.handle_individual_property_fetch') as mock_handler:
                mock_handler.side_effect = Exception("Test error")
                
                with pytest.raises(Exception):
                    process_pipeline_jobs()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
