#!/usr/bin/env python3
"""
Main application entry point for the Real Estate Data Pipeline.

This script orchestrates the entire data collection and processing pipeline.
"""

import sys
import os
from datetime import timedelta

# Add the project directory to the path so we can import the modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.connection import SessionLocal, Pipline_Tables
from create_new_zip import create_or_change_zip
from src.pipeline.scheduler import populate_sold_and_for_sale_queues
from src.pipeline.runner import process_pipeline_jobs
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main function to run the real estate data pipeline."""
    logger.info("Starting Real Estate Data Pipeline")
    
    try:
        # Configure zipcode for data collection
        # logger.info("Configuring zipcode settings...")
        # create_or_change_zip(
        #     zipcode="85297",
        #     sold_fetch_frequency=timedelta(days=7),
        #     for_sale_fetch_frequency=timedelta(days=1)
        # )
        
        # Populate job queues
        logger.info("Populating job queues...")
        populate_sold_and_for_sale_queues()
        
        # Process all pipeline jobs
        logger.info("Processing pipeline jobs...")
        while True:
            session = SessionLocal()
            try:
                has_any = session.query(Pipline_Tables).first() is not None
                if not has_any:
                    break
                process_pipeline_jobs()
            finally:
                session.close()
        
        logger.info("All pipeline jobs have been processed successfully")
        
    except Exception as e:
        logger.error(f"Pipeline failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
