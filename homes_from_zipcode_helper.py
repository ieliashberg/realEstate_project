from dataBase import SessionLocal, Zipcodes, Property, Property_Change, Transaction, Listing, Status_History, Price_History
from user_agents import get_ua
from playwright.sync_api import sync_playwright
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timezone, timedelta
from sqlalchemy import inspect
from http_handling_utils import fetch_html_via_https, strip_json_beginning

import json
import time

import logging

# configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fetch_homes_json_from_zipcode(pipeline_name: str, zipcode: str):
    session = SessionLocal()
    try:
        # try the database
        record = (
            session.query(Zipcodes)
            .filter(Zipcodes.zipcode == zipcode)
            .one_or_none()
        )

        if record and record.for_sale_request_url and pipeline_name == "for_sale_homes_fetch":
            homes_response = fetch_html_via_https(record.for_sale_request_url)
            homes_response = strip_json_beginning(homes_response)

        elif record and record.sold_request_url and pipeline_name == "sold_homes_fetch":
            homes_response = fetch_html_via_https(record.sold_request_url)
            homes_response = strip_json_beginning(homes_response)

        # database miss or other error so fall back to playwright fetch
        else:
            url = "https://www.redfin.com/zipcode/" + str(zipcode)
            if pipeline_name == "sold_homes_fetch":
                url = url + "/filter/include=sold-3mo"
            homes_response, request_url = fetch_homes_json_via_playwright(url)

            # persist for next time
            existing_zip_row = session.get(Zipcodes, zipcode)
            if pipeline_name == "for_sale_homes_fetch":
                existing_zip_row.for_sale_request_url = request_url
                existing_zip_row.last_for_sale_fetch = datetime.now(timezone.utc)
            else:
                existing_zip_row.sold_request_url = request_url
                existing_zip_row.last_sold_fetch = datetime.now(timezone.utc)

            session.commit()

        if homes_response.get("errorMessage") == "Success":
            homes = homes_response.get("payload", {}).get("homes")
            return homes
        else:
            logger.error(f"Could not go to zipcode {zipcode}, error = {homes_response.get("errorMessage")}")
            return []


    except SQLAlchemyError as db_err:
        session.rollback()
        # log the error, or re-raise if you want upstream handling
        print(f"[DB ERROR] could not update zip_to_bounds for {zipcode}: {db_err}")
        raise

    except Exception as e:
        session.rollback()
        # handle playwright or other failures if you like
        print(f"[ERROR] fetch_bounds_for_zip({zipcode}) failed: {e}")
        raise

    finally:
        session.close()


def fetch_homes_json_via_playwright(page_url):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent=get_ua()
        )
        page = context.new_page()

        # wait until network is quiet
        page.goto(page_url)
        time.sleep(1)

        # 2) Prepare to catch the GIS response
        #    The lambda will be evaluated on every response: we pick the one whose URL contains "/stingray/api/gis"
        with page.expect_response(lambda response: "/stingray/api/gis?" in response.url, timeout=10_000) as resp_info:
            # 3) Trigger the map‐refresh that fires that request
            page.click("[data-rf-test-id='map-zoom-control-minus'] button")
        gis_response = resp_info.value
        gis_request_url = gis_response.url

        raw_text = gis_response.text()
        if raw_text.startswith("{}&&"):
            raw_text = raw_text.split("&&", 1)[1]
        gis_payload = json.loads(raw_text)

        browser.close()
        return gis_payload, gis_request_url


def upsert_initial_info(session, home):
    try:
        payload = upsert_property(home, session)
        listing_id = upsert_listing(home, payload.get("property_id"), session)
        payload["listing_id"] = listing_id
        return payload
    except Exception:
        session.rollback()


def upsert_property(home, session):
    new_prop = Property(  # .get everywhere gives us safe retrieval in case doesn't exist
        redfin_property_id=home.get('propertyId'),
        address=home.get('streetLine', {}).get('value'),
        city=home.get('city'),
        state=home.get('state'),
        zipcode=home.get('zip'),
        latitude=home.get('latLong', {}).get('value', {}).get('latitude'),
        longitude=home.get('latLong', {}).get('value', {}).get('longitude'),
        lot_size=home.get('lotSize', {}).get('value'),
        year_built=home.get('yearBuilt', {}).get('value'),
        property_type=home.get('uiPropertyType'),  # ex: home, condo, townhouse, multifamily, land, mobile
        beds=home.get('beds'),
        baths=home.get('baths'),
        sqft=home.get('sqFt', {}).get('value'),
        stories=home.get('stories'),
        unit_number=home.get('unitNumber', {}).get('value'),
        hoa=home.get('hoa', {}).get('value'),
        builder_name=home.get('newConstructionCommunityInfo', {}).get('builderName'),
        is_on_market=(home.get('mlsStatus') != "Closed" and home.get('mlsStatus') != "Sold")
    )

    try:
        old_prop = session.query(Property) \
            .filter_by(redfin_property_id=new_prop.redfin_property_id) \
            .first()
        if old_prop:
            mapper = inspect(old_prop.__class__)
            #  iterate through all column-based attributes
            for attr in mapper.attrs:
                # columnProperty attributes have .columns
                if hasattr(attr, 'columns'):
                    col = attr.columns[0]
                    if col.primary_key:
                        continue  # skip pk field
                    name = attr.key
                    old_val = getattr(old_prop, name)
                    new_val = getattr(new_prop, name)
                    if old_val != new_val and new_val is not None:
                        session.add(Property_Change(
                            property_id=old_prop.property_id,
                            changed_attribute=name,
                            change_date=datetime.now(timezone.utc),
                            old_value=str(old_val),
                            new_value=str(new_val),
                            source="redfin",
                        ))
                        setattr(old_prop, name, new_val)
                        logger.info(
                            f"Updating Property_Change table. Name of changed attribute = {name}, oldVal = {old_val}, newVal = {new_val} (redfin_id={new_prop.redfin_property_id}, property_id = {new_prop.property_id})")

            # if it was on the market before and now current mlsStatus is "sold"
            if old_prop.is_on_market and home.get('mlsStatus') == "Sold":
                # update the transaction table
                session.add(Transaction(
                    property_id=old_prop.property_id,
                    transaction_date=datetime.fromtimestamp(home.get('soldDate')/1000, tz=timezone.utc),
                    transaction_type="Sold",
                    price=home.get('price', {}).get('value')
                ))
                logger.info(
                    f"Updated transaction table, redfin_id={new_prop.redfin_property_id}, property_id = {new_prop.property_id} sold for {home.get('price', {}).get('value')}")
            payload = {
                "city": old_prop.city,
                "state": old_prop.state,
                "address": old_prop.address,
                "zipcode": old_prop.zipcode,
                "redfin_property_id": old_prop.redfin_property_id,
                "property_id": old_prop.property_id,
                "isNewProperty": False
            }
        else:
            session.add(new_prop)
            session.flush()     # gives newProperty.property_id

            logger.info(f"Inserting new property (redfin_id={new_prop.redfin_property_id}, property_id = {new_prop.property_id})")

            payload = {
                "city": new_prop.city,
                "state": new_prop.state,
                "address": new_prop.address,
                "zipcode": new_prop.zipcode,
                "redfin_property_id": new_prop.redfin_property_id,
                "property_id": new_prop.property_id,
                "isNewProperty": True

            }

        session.commit()
        return payload
    except Exception as e:
        logger.exception("Error inserting property:", e)
        session.rollback()
        raise

    finally:
        session.close()


def upsert_listing(home, propertyID, session):
    new_list = Listing(
        property_id=propertyID,
        redfin_listing_id=home.get('listingId'),
        list_date=get_list_date(home),
        current_status=home.get('mlsStatus'),       # mls listing, ex: Active, closed, pending etc.)
        url="https://www.redfin.com" + home.get('url'),
        isNewConstruction=home.get('isNewConstruction'),
        current_price=home.get('price', {}).get('value')
    )

    try:
        listing_id = None
        old_list = session.query(Listing)\
               .filter_by(property_id=propertyID)\
               .first()

        if old_list:
            # if current status is not the same as previous status, update status history table
            if old_list.current_status != new_list.current_status:
                session.add(Status_History(
                    listing_id=old_list.listing_id,
                    change_date=datetime.now(timezone.utc),
                    old_status=old_list.current_status,
                    new_status=new_list.current_status,
                    source="redfin"
                ))
                setattr(old_list, 'current_status', new_list.current_status)

            # if the curr price is not the same as prev price, update price history table
            if old_list.current_price != new_list.current_price:
                session.add(Price_History(
                    listing_id=old_list.listing_id,
                    change_date=datetime.now(timezone.utc),
                    old_price=old_list.current_price,
                    new_price=new_list.current_price,
                    source="redfin"
                ))
                setattr(old_list, 'current_price', new_list.current_price)
            listing_id = old_list.listing_id

        else:
            session.add(new_list)
            session.flush()  # gives new_listing.listing_id
            listing_id = new_list.listing_id

        return listing_id
    except Exception as e:
        session.rollback()
        logger.exception("Error inserting listing:", e)
        raise


def get_list_date(home):
    raw = home.get('dom', {}).get('value')
    if raw is None:
        return None   # or some sensible default

    try:
        dom = int(raw)
    except (TypeError, ValueError):
        return None
    date = datetime.now(timezone.utc) - timedelta(days=dom)
    return date.isoformat()[:10]
