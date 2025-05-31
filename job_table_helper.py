from datetime import datetime, timezone
from dataBase import Pipline_Tables
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def enqueue_job(session, pipeline_name: str, payload: dict):
    new_row = Pipline_Tables(
        name_of_pipeline=pipeline_name,
        payload=payload,
        enqueued_at=datetime.now(timezone.utc)
    )
    session.add(new_row)
    session.commit()
