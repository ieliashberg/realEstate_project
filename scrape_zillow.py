import json
from get_homes_info import get_homes_info
from zestimate_helper import get_zestimate
from load_to_db import load_to_db
from populate_sold_and_for_sale_queues import populate_sold_and_for_sale_queues
from job_runner import process_pipeline_jobs
from datetime import timedelta
from create_new_zip  import create_or_change_zip
from dataBase import SessionLocal, Pipline_Tables


def main():
    # create_or_change_zip(zipcode="85297",
    #                     sold_fetch_frequency=timedelta(days=7),
    #                     for_sale_fetch_frequency=timedelta(days=1))
    #
    # populate_sold_and_for_sale_queues()
    process_pipeline_jobs()


if __name__ == "__main__":
    main()
