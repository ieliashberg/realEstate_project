#!/usr/bin/env python3
"""
Test script to verify error handling in process_pipeline_jobs.
"""

import logging
from dataBase import SessionLocal, Pipline_Tables
from datetime import datetime, timezone
from job_runner import process_pipeline_jobs, MAX_RETRIES

# Configure logging to see detailed output
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_test_job(pipeline_name: str, payload: dict) -> int:
    """Create a test job and return its ID."""
    session = SessionLocal()
    try:
        job = Pipline_Tables(
            name_of_pipeline=pipeline_name,
            payload=payload,
            enqueued_at=datetime.now(timezone.utc)
        )
        session.add(job)
        session.commit()
        job_id = job.id
        logger.info(f"Created test job {job_id} with pipeline '{pipeline_name}'")
        return job_id
    finally:
        session.close()

def check_job_status(job_id: int) -> dict:
    """Check the current status of a job."""
    session = SessionLocal()
    try:
        job = session.query(Pipline_Tables).filter(Pipline_Tables.id == job_id).first()
        if job:
            return {
                "exists": True,
                "payload": job.payload,
                "retry_count": job.payload.get("_retry_count", 0),
                "last_error": job.payload.get("_last_error"),
                "next_retry_at": job.payload.get("_next_retry_at")
            }
        else:
            return {"exists": False}
    finally:
        session.close()

def cleanup_test_jobs():
    """Clean up any remaining test jobs."""
    session = SessionLocal()
    try:
        # Delete jobs with test payloads
        test_jobs = session.query(Pipline_Tables).filter(
            Pipline_Tables.payload.op('->>')('test') == 'true'
        ).all()
        
        for job in test_jobs:
            session.delete(job)
            logger.info(f"Cleaned up test job {job.id}")
        
        session.commit()
    finally:
        session.close()

def test_unknown_pipeline_handler():
    """Test that unknown pipeline handlers are properly handled."""
    logger.info(" Testing unknown pipeline handler...")
    
    job_id = create_test_job("unknown_pipeline", {"test": "true", "data": "test"})
    
    # Process jobs
    process_pipeline_jobs()
    
    # Check that the job was deleted
    status = check_job_status(job_id)
    if not status["exists"]:
        logger.info(" Unknown pipeline job was properly deleted")
    else:
        logger.error(" Unknown pipeline job was not deleted")

def test_job_retry_logic():
    """Test that failed jobs are retried with exponential backoff."""
    logger.info(" Testing job retry logic...")
    
    # Create a job that will fail (invalid zipcode)
    job_id = create_test_job("sold_homes_fetch", {
        "test": "true",
        "zipcode": "invalid_zipcode"
    })
    
    # Process jobs once
    process_pipeline_jobs()
    
    # Check that the job was retried
    status = check_job_status(job_id)
    if status["exists"] and status["retry_count"] == 1:
        logger.info(f" Job retry logic working - retry_count: {status['retry_count']}")
        logger.info(f"   Next retry at: {status['next_retry_at']}")
        logger.info(f"   Last error: {status['last_error']}")
    else:
        logger.error(f" Job retry logic not working - status: {status}")

def test_max_retries():
    """Test that jobs are deleted after max retries."""
    logger.info(" Testing max retries...")
    
    # Create a job that will fail
    job_id = create_test_job("individual_property_fetch", {
        "test": "true",
        "property_id": "invalid_property",
        "address": "invalid",
        "city": "invalid",
        "state": "invalid",
        "zipcode": "invalid"
    })
    
    # Process jobs multiple times to exceed max retries
    for attempt in range(MAX_RETRIES + 2):
        logger.info(f"Processing attempt {attempt + 1}...")
        process_pipeline_jobs()
        
        status = check_job_status(job_id)
        if not status["exists"]:
            logger.info(f" Job was deleted after {attempt + 1} attempts")
            break
        elif status["retry_count"] >= MAX_RETRIES:
            logger.info(f" Job reached max retries ({MAX_RETRIES})")
            break
        else:
            logger.info(f"   Job retry count: {status['retry_count']}")
    
    # Final check
    final_status = check_job_status(job_id)
    if not final_status["exists"]:
        logger.info(" Job was properly deleted after max retries")
    else:
        logger.error(f" Job still exists after max retries: {final_status}")

def main():
    """Run all error handling tests."""
    logger.info(" Starting error handling tests...")
    
    try:
        # Clean up any existing test jobs
        cleanup_test_jobs()
        
        # Run tests
        test_unknown_pipeline_handler()
        cleanup_test_jobs()
        
        test_job_retry_logic()
        cleanup_test_jobs()
        
        test_max_retries()
        cleanup_test_jobs()
        
        logger.info(" All error handling tests completed!")
        
    except Exception as e:
        logger.exception(f" Test failed with error: {e}")
    finally:
        # Final cleanup
        cleanup_test_jobs()

if __name__ == "__main__":
    main()
