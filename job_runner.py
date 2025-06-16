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
            session.close()
            continue

        try:
            if job.name_of_pipeline in ("sold_homes_fetch", "for_sale_homes_fetch"):
                handler(job.name_of_pipeline, job.payload)
            else:
                handler(job.payload)

            session.delete(job)
            session.commit()
            logger.info(f"Job {job.id} succeeded and was deleted")
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
    logger.info(f"Handling individual property fetch for {property_id}")
    extra_info = get_specific_property_info(payload)
    session = SessionLocal()

    upsert_more_info(session, extra_info, payload.get("property_id"), payload.get("listing_id"), payload.get("isNewProperty"))
    session.commit()
    session.close()


def handle_fetch_zestimate(payload: dict):
    property_id = payload.get("property_id")
    logger.info(f"Handling fetch zestimates for property_id {property_id}")
    zestimate, zestimate_high, zestimate_low = get_zestimate(payload.get("address"), payload.get("city"), payload.get("state"), payload.get("zipcode"))
    session = SessionLocal()
    upsert_zestimates(session, property_id, zestimate, zestimate_high, zestimate_low)
    session.commit()
    session.close()


# Map pipeline names to handlers
PIPELINE_HANDLERS = {
    "sold_homes_fetch": handle_sold_or_for_sale_homes_fetch,
    "for_sale_homes_fetch": handle_sold_or_for_sale_homes_fetch,
    "individual_property_fetch": handle_individual_property_fetch,
    "fetch_zestimate": handle_fetch_zestimate,
}