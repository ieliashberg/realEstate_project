from dataBase import SessionLocal, Pipline_Tables
from homes_from_zipcode_helper import fetch_homes_json_from_zipcode, upsert_initial_info
from specfic_home_info_helper import get_specific_property_info, upsert_more_info
from job_table_helper import enqueue_job
import logging

# configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ----- Processing queued jobs -----
def process_pipeline_jobs():
    session = SessionLocal()
    try:
        # fetch all jobs
        jobs = session.query(Pipline_Tables).all()
        for job in jobs:
            handler = PIPELINE_HANDLERS.get(job.name_of_pipeline)
            if handler:
                try:
                    # pass both pipeline name and payload to the handler
                    if job.name_of_pipeline in ("sold_homes_fetch", "for_sale_homes_fetch"):
                        handler(job.name_of_pipeline, job.payload)
                    else:
                        handler(job.payload)
                    # delete job on success
                    session.delete(job)
                except Exception:
                    logger.exception(f"Error processing job id={job.id} pipeline={job.name_of_pipeline}")
            else:
                logger.warning(f"No handler for pipeline '{job.name_of_pipeline}' (job id={job.id})")
        session.commit()
        logger.info("Processed all pipeline jobs.")
    except Exception:
        session.rollback()
        logger.exception("Failed processing pipeline jobs.")
        raise
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
    logger.info(f"Handling individual property fetch for {property_id}")
    extra_info = get_specific_property_info(payload)
    session = SessionLocal()

    upsert_more_info(session, extra_info, payload.get("property_id"), payload.get("listing_id"), payload.get("isNewProperty"))
    session.close()


def handle_fetch_zestimate(payload: dict):
    property_id = payload.get("property_id")
    logger.info(f"Handling fetch zestimates for {property_id}")
    # zestimates = get_zestimate(payload)
    # session = SessionLocal()
    # upsert_zestimate(session, zestimates)
    # session.close()


# Map pipeline names to handlers
PIPELINE_HANDLERS = {
    "sold_homes_fetch": handle_sold_or_for_sale_homes_fetch,
    "for_sale_homes_fetch": handle_sold_or_for_sale_homes_fetch,
    "individual_property_fetch": handle_individual_property_fetch,
    "fetch_zestimate": handle_fetch_zestimate,
}