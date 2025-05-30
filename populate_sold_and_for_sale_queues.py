from datetime import datetime, timezone
from dataBase import SessionLocal, Zipcodes
from job_table_helper import enqueue_job
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def populate_sold_and_for_sale_queues():
    """
    Iterate over all ZIP codes in Zipcodes table and enqueue
    for_sale_homes_fetch or sold_homes_fetch whenever due.
    """
    num_sold_enqueued = 0
    num_for_sale_enqueued = 0
    session = SessionLocal()
    now = datetime.now(timezone.utc)
    try:
        # load all zip rows
        zip_rows = session.query(Zipcodes).all()
        for zip_row in zip_rows:
            # for-sale
            last_sale_fetch = zip_row.last_for_sale_fetch or datetime.fromtimestamp(0, tz=timezone.utc)
            next_for_sale_fetch = last_sale_fetch + zip_row.for_sale_fetch_frequency
            if now >= next_for_sale_fetch:
                enqueue_job(session, "for_sale_homes_fetch", {"zipcode": zip_row.zipcode})
                num_for_sale_enqueued += 1

                logging.info(f"Enqueued for_sale_homes_fetch for {zip_row.zipcode}")
                zip_row.last_for_sale_fetch = now

            # sold
            last_sold_fetch = zip_row.last_sold_fetch or datetime.fromtimestamp(0, tz=timezone.utc)
            next_sold_fetch = last_sold_fetch + zip_row.sold_fetch_frequency
            if now >= next_sold_fetch:
                enqueue_job(session, "sold_homes_fetch", {"zipcode": zip_row.zipcode})
                num_sold_enqueued += 1

                logging.info(f"Enqueued sold_homes_fetch for {zip_row.zipcode}")
                zip_row.last_sold_fetch = now

        session.commit()
        logging.info(f"Scheduled {num_for_sale_enqueued} sold and {num_sold_enqueued} for sale fetch jobs for zipcodes.")
    except Exception:
        session.rollback()
        logging.exception("Error scheduling fetch jobs for all zipcodes.")
        raise
    finally:
        session.close()