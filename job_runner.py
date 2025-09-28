from dataBase import SessionLocal, Pipline_Tables
from homes_from_zipcode_helper import fetch_homes_json_from_zipcode, upsert_initial_info
from specfic_home_info_helper import get_specific_property_info, upsert_more_info
from job_table_helper import enqueue_job
from zestimate_helper import get_zestimate, upsert_zestimates
import logging

# configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ----- Processing queued jobs -----
def process_pipeline_jobs():
    while True:
        session = SessionLocal()
        job = session.query(Pipline_Tables).order_by(Pipline_Tables.id).first()
        if not job:
            session.close()
            break

        handler = PIPELINE_HANDLERS.get(job.name_of_pipeline)
        if not handler:
            logger.warning(f"No handler for {job.name_of_pipeline}, deleting job {job.id}")
            session.delete(job)
            session.commit()
            logger.info(f"DATABASE DELETE: Job {job.id} ({job.name_of_pipeline}) - No handler found")
            session.close()
            continue

        try:
            if job.name_of_pipeline in ("sold_homes_fetch", "for_sale_homes_fetch"):
                handler(job.name_of_pipeline, job.payload)
            else:
                handler(job.payload)

            session.delete(job)
            session.commit()
            logger.info(f"DATABASE DELETE: Job {job.id} ({job.name_of_pipeline}) - Completed successfully")
        except Exception:
            session.rollback()
            logger.exception(f"Job {job.id} failed—rolled back, leaving it for retry")
        finally:
            session.close()


def handle_sold_or_for_sale_homes_fetch(pipeline: str, payload: dict):
    """
    Unified handler for both sold_homes_fetch and for_sale_homes_fetch.
    """
    # fetch homes basic json
    homes = fetch_homes_json_from_zipcode(pipeline, payload.get("zipcode"))
    session = SessionLocal()
    for home in homes:
        # upsert property and get payload for next specific_info job scheduling

        payload = upsert_initial_info(session, home)

        # put job into queue to get specific info
        enqueue_job(session, "individual_property_fetch", payload)
        enqueue_job(session, "fetch_zestimate", payload)

    session.commit()
    session.close()


def handle_individual_property_fetch(payload: dict):
    property_id = payload.get("property_id")
    address = payload.get("address", "Unknown")
    city = payload.get("city", "Unknown")
    state = payload.get("state", "Unknown")
    zipcode = payload.get("zipcode", "Unknown")
    
    try:
        extra_info = get_specific_property_info(payload)
        
        if extra_info is None:
            logger.error(f"REDFIN FAILED: No data received for {address}, {city}, {state} {zipcode}")
            return
        
        tax_annual_amount = extra_info['tax_annual_amount']
        
        if tax_annual_amount:
            logger.info(f"REDFIN SUCCESS: {address}, {city}, {state} {zipcode} - Tax: ${tax_annual_amount:,}, Schools: {len(extra_info.get('schools', []))}, Price History: {len(extra_info.get('price_history', []))}")
        else:
            logger.warning(f"REDFIN NO DATA: {address}, {city}, {state} {zipcode} - No tax information available; Available data: {extra_info}")
            
        session = SessionLocal()
        upsert_more_info(session, extra_info, payload.get("property_id"), payload.get("listing_id"), payload.get("isNewProperty"))
        session.commit()
        session.close()
        
    except Exception as e:
        logger.error(f"REDFIN FAILED: Exception for {address}, {city}, {state} {zipcode} - {type(e).__name__}: {e}")
        raise


def handle_fetch_zestimate(payload: dict):
    property_id = payload.get("property_id")
    address = payload.get("address")
    city = payload.get("city")
    state = payload.get("state")
    zipcode = payload.get("zipcode")
    
    try:
        zestimate, zestimate_high, zestimate_low = get_zestimate(address, city, state, zipcode)
        
        # Check if we got valid data
        if zestimate is None and zestimate_high is None and zestimate_low is None:
            # Don't raise exception - just log and continue
            # This prevents the job from being retried indefinitely
            return
        
        session = SessionLocal()
        try:
            upsert_zestimates(session, property_id, zestimate, zestimate_high, zestimate_low)
            session.commit()
        except Exception as e:
            session.rollback()
            raise  # Re-raise to trigger job retry
        finally:
            session.close()
            
    except Exception as e:
        raise  # Re-raise to trigger job retry


# Map pipeline names to handlers
PIPELINE_HANDLERS = {
    "sold_homes_fetch": handle_sold_or_for_sale_homes_fetch,
    "for_sale_homes_fetch": handle_sold_or_for_sale_homes_fetch,
    "individual_property_fetch": handle_individual_property_fetch,
    "fetch_zestimate": handle_fetch_zestimate,
}