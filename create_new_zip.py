from datetime import datetime, timezone, timedelta
from src.database.connection import SessionLocal, Zipcodes
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_or_change_zip(zipcode: str, for_sale_fetch_frequency: timedelta, sold_fetch_frequency: timedelta):
    session = SessionLocal()
    try:
        # load or instantiate
        # zipcode kept in string format in case of leading 0s
        row = session.get(Zipcodes, zipcode)
        changes_made = False
        if row is None:
            row = Zipcodes(zipcode=zipcode)
            session.add(row)
            changes_made=True

        if not isinstance(for_sale_fetch_frequency, timedelta):
            raise ValueError("for_sale_fetch_frequency must be a timedelta")

        if not isinstance(sold_fetch_frequency, timedelta):
            raise ValueError("sold_fetch_frequency must be a timedelta")

        # Check if frequencies need updating
        if row.for_sale_fetch_frequency_days != for_sale_fetch_frequency.days:
            row.for_sale_fetch_frequency_days = for_sale_fetch_frequency.days
            changes_made = True

        if row.sold_fetch_frequency_days != sold_fetch_frequency.days:
            row.sold_fetch_frequency_days = sold_fetch_frequency.days
            changes_made = True

        session.commit()
        if changes_made:
            logger.info(f"Upserted ZIP {zipcode}: "
                        f"for_sale fetched every {for_sale_fetch_frequency}, "
                        f"sold fetched every {sold_fetch_frequency}")

        else:
            logger.info(f"No changes made to zipcode {zipcode}: "
                        f"for_sale fetched every {for_sale_fetch_frequency}, "
                        f"sold fetched every {sold_fetch_frequency}")
    except Exception:
        session.rollback()
        logger.exception(f"Failed to upsert ZIP {zipcode}")
        raise

    finally:
        session.close()

