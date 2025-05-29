from datetime import datetime, timezone, timedelta
from dataBase import SessionLocal, Zipcodes
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_or_change_zip(zipcode: str, for_sale_fetch_frequency: timedelta, sold_fetch_frequency: timedelta):
    session = SessionLocal()
    try:
        # load or instantiate
        # zipcode kept in string format in case of leading 0s
        row = session.get(Zipcodes, zipcode)
        if row is None:
            row = Zipcodes(zipcode=zipcode)
            session.add(row)

        if not isinstance(for_sale_fetch_frequency, timedelta):
            raise ValueError("for_sale_fetch_frequency must be a timedelta")

        if not isinstance(sold_fetch_frequency, timedelta):
            raise ValueError("sold_fetch_frequency must be a timedelta")

        row.for_sale_fetch_frequency = for_sale_fetch_frequency
        row.sold_fetch_frequency = sold_fetch_frequency
        row.last_updated = datetime.now(timezone.utc)

        session.commit()
        logger.info(f"Upserted ZIP {zipcode}: "
                    f"for_sale fetched every {for_sale_fetch_frequency}, "
                    f"sold fetched every {sold_fetch_frequency}")

    except Exception:
        session.rollback()
        logger.exception(f"Failed to upsert ZIP {zipcode}")
        raise

    finally:
        session.close()

