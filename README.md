# Real Estate Data Pipeline

A Python-based scraping and ETL pipeline for aggregating real estate data from Redfin and Zillow. This project automatically:

1. **Fetches “For Sale” and “Sold” home listings** per ZIP code (via Redfin).
2. **Extracts detailed property information** (schools, price history, taxes, agents, etc.) for each listing.
3. **Fetches Zillow rent estimates (Zestimates)** for individual properties.
4. **Stores everything in a PostgreSQL database** and maintains historical records (price history, transaction history, zestimate history, etc.).
5. **Queues and schedules jobs** so that ZIP-level fetches run at configurable intervals, and per-property tasks (detailed info, zestimate updates) chain automatically.
6. **Handles cookies, and anti-bot measures** (Playwright + rotating UA + stealth script to get original cookie; then raw http request for later fetches until cookie stops working).

---

## Main scripts
 - create_or_change_zip(zipcode: str, sold_fetch_frequency: timedelta, for_sale_fetch_frequency: timedelta)
   - Upserts a zipcode into the database to scrape
 - populate_sold_and_for_sale_queues()
   - goes through all zipcodes and enqueues (into pipeline_tables) whichever ones need to be scraped (either for sold properties or for sale properties or both)
 - process_pipeline_jobs()
   - goes through current job list in pipline_tables and completes every job (some jobs enque other jobs which are not run until the "first round" of jobs finish 

## Prerequisites

- **Python 3.10+** (tested on 3.11/3.12)  
- **PostgreSQL** (v12+)  
- **WebKit/Chromium dependencies** (for Playwright headless):  
  - On macOS:  
    Playwright’s `brew install` is usually sufficient (see Playwright docs).  
- **Node.js & npm** (for Playwright installation)  
- **Browser binaries** (installed via `playwright install`)  
