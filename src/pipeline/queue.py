from datetime import datetime, timezone
from ..database.connection import Pipline_Tables
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def enqueue_job(session, pipeline_name: str, payload: dict):
    new_row = Pipline_Tables(
        job_type=pipeline_name,
        payload=json.dumps(payload) if payload else None,
        status='pending'
    )
    session.add(new_row)
    session.commit()
