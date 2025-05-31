from dataBase import Property, Transaction, Listing, School, Price_History, Property_School_Join
from sqlalchemy.exc import SQLAlchemyError, NoResultFound
from datetime import datetime, timezone, timedelta
from http_handling_utils import fetch_html_via_https, redfin_base_headers
import re
import json
import logging

# configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_url(payload: json):
    payload['address'] = payload.get('address').replace(" ", "-")
    payload['address'] = payload.get('address').lower()
    payload['address'] = payload.get('city').lower()
    payload['address'] = payload.get('state').lower()
    url = f"https://www.redfin.com/{payload.get('state')}/{payload.get('city')}/{payload.get('address')}-{payload.get('zip')}/home/{payload.get('redfin_property_id')}"
    return url


def get_specific_property_info(payload: json):
    url = create_url(payload)
    extra_info = None
    try:
        html = fetch_html_via_https(url, redfin_base_headers)
        if not html:
            raise

        data = get_property_json(html)
        agent_info = get_agent_info(data)
        extra_info = {
            "schools": get_schools(data),
            "price_history": get_price_history(data),
            "covered_spaces": get_covered_spaces(data),
            "tax_annual_amount": get_tax_annual(data),
            "agents_name": agent_info.get('agent_name'),
            "agents_broker": agent_info.get('agent_broker'),
        }

    except Exception as e:
        logger.error(f"[ERROR] processing {url} raised {type(e).__name__}: {e}")

    return extra_info


def upsert_more_info(session, extra_info: json, propertyID, listingID, isNewProperty):
    # fetch property to update
    try:
        prop = session.query(Property).filter_by(property_id=propertyID).one()
    except NoResultFound:
        raise RuntimeError(f"Property {propertyID} not found")

    # update necessary info for property
    cv = extra_info.get("covered_spaces")
    if cv is not None:
        try:
            prop.covered_spaces = int(float(cv))
        except (TypeError, ValueError):
            prop.covered_spaces = None

    tx = extra_info.get("tax_annual_amount")
    if tx is not None:
        try:
            prop.tax_annual_amount = int(float(tx))
        except (TypeError, ValueError):
            prop.tax_annual_amount = None

    session.flush()

    # fetch & update Listing
    try:
        lst = session.query(Listing).filter_by(listing_id=listingID).one()
    except NoResultFound:
        raise RuntimeError(f"Listing {listingID} not found")

    lst.agent_name = extra_info.get("agents_name")
    lst.agent_broker = extra_info.get("agents_broker")
    session.flush()

    # upsert schools & joins
    for school in extra_info.get("schools", []):
        school_id = upsert_school(school, session)
        upsert_property_school(propertyID, school_id, school, session)
    session.flush()

    # bootstrap sold‐transaction history
    #    We only pass the list of events; bootstrap_sold_histories
    #    will skip non-sold markers and avoid duplicates if you’ve written it that way.
    if isNewProperty:
        bootstrap_price_histories(listingID,
                                  extra_info.get("price_history", []),
                                  session)
        bootstrap_sold_histories(propertyID,
                                 extra_info.get("price_history", []),
                                 session)

    # leave commit to caller


def bootstrap_price_histories(listing_id, price_history, session):
    try:
        slice_entries = []
        for entry in price_history:
            description = entry.get("description", "")
            if "Sold" in description:
                break
            slice_entries.append(entry)

        # 1) Determine the initial old_price from the last "Listed (Active)"
        initial_price = None
        for entry in reversed(slice_entries):
            if entry.get("description") == "Listed (Active)":
                initial_price = entry.get('price')
                break

        # 2) Pull out only the Price Changed entries, then reverse to oldest -> newest
        changes = [
            e for e in slice_entries
            if e.get("description") == "Price Changed"
        ]
        changes.reverse()

        # add to table
        prev_price = initial_price
        for entry in changes:
            this_price = entry.get("price")
            session.add(Price_History(
                listing_id=listing_id,
                change_date=entry.get("date"),
                old_price=prev_price,
                new_price=this_price,
                source="redfin"
            ))
            prev_price = this_price
        session.flush()
        logger.info("Finished bootstrapping price history")
        return
    except Exception:
        logger.exception("Error bootstrapping price histories")
        session.rollback()
        raise


def upsert_property_school(property_id: int, school_id: int, school, session):
    dist = school.get('dist')
    new_prop_school = Property_School_Join(
        property_id=property_id,
        school_id=school_id,
        distance=dist
    )
    try:
        old_prop_school = session.query(Property_School_Join) \
            .filter_by(property_id=property_id, school_id=school_id) \
            .first()
        if not old_prop_school:
            session.add(new_prop_school)

        elif old_prop_school.distance != dist:
            old_prop_school.distance = dist
            old_prop_school.last_updated = datetime.now(timezone.utc)

    except Exception:
        logger.exception("Error upserting property_school")
        session.rollback()
        raise


def bootstrap_sold_histories(property_id, price_history, session):
    sold_markers = (
        "Sold (Public Records)",
        "Sold (MLS)",
        "Sold (MLS) (Closed)",
        "Sold (MLS) (Sold)",
    )

    try:
        last_sale_date = None

        for entry in price_history:
            description = entry.get("description", "")
            # only care about sold events
            if not any(description == marker for marker in sold_markers):
                continue

            dt = datetime.strptime(entry["date"], "%Y-%m-%d").date()

            # skip if too close to the last recorded sale
            if last_sale_date and (last_sale_date - dt) < timedelta(days=45):
                continue

            # create the Transaction
            new_transaction = Transaction(
                property_id=property_id,
                transaction_date=dt,
                transaction_type=description,
                price=entry.get('price'),
            )
            session.add(new_transaction)

            # remember this date for next loop
            last_sale_date = dt

        session.flush()
        logger.info("Finished bootstrapping sold history")
    except Exception:
        logger.exception("Error bootstrapping sold histories")
        raise


def upsert_school(school, session) -> int:
    """
    Insert or update a School and always return its school_id.
    """
    existing = (
        session
        .query(School)
        .filter_by(name=school['name'])
        .first()
    )
    if not existing:
        new_school = School(
            name=school.get('name'),
            rating=school.get('rating'),
            is_public=school.get('is_public'),
            is_elementary=school.get('is_elementary'),
            is_middle=school.get('is_middle'),
            is_high=school.get('is_high'),
        )
        session.add(new_school)
        session.flush()  # populates new_school.school_id
        return new_school.school_id
    else:
        # update if needed
        updated = False
        if existing.rating != school.get('rating'):
            existing.rating = school.get('rating')
            updated = True
        if updated:
            session.flush()
        return existing.school_id


def get_property_json(html):
    m = re.search(
        r'belowTheFold".*?"text"\s*:\s*"((?:\\.|[^"\\])*)"',  # search for the json dump
        html,
        flags=re.DOTALL
    )
    if not m:
        raise RuntimeError("Couldn't find the belowTheFold text block")

    raw = m.group(1)

    # un-escape JavaScript-style unicode (e.g. \u002F → /) and other escapes
    #    (this also turns \\n, \\" etc. into real newlines and quotes)
    decoded = bytes(raw, 'utf-8').decode('unicode_escape')

    # strip off the "{}&&" prefix that Redfin tacks on to avoid XSSI
    if decoded.startswith('{}&&'):
        decoded = decoded.split('&&', 1)[1]

    # parse into json
    return json.loads(decoded).get("payload")


def clean_price(input_str: str):
    # drop '(' and everything after
    s = input_str.split('(')[0]
    # remove any word starting with '\u' up to the next space
    s = re.sub(r'\\u[^ ]*', '', s)
    # strip leading dollar sign
    if s.startswith('$'):
        s = s[1:]
    # remove all commas
    s = s.replace(',', '')
    if s == "\u2014":
        s = ""
    # trim whitespace
    s = s.strip()

    try:
        # handle floats just in case
        return int(float(s))
    except ValueError:
        return None


def get_schools(data):
    schools = []
    schools_json = data.get("schoolsAndDistrictsInfo", {}).get("servingThisHomeSchools") or []
    for school in schools_json:
        is_public = False
        is_elementary = False
        is_middle = False
        is_high = False

        name = school.get("name")
        rating = school.get("greatSchoolsRating")
        distance_mi = school.get("distanceInMiles")

        institutionType = school.get("institutionType")
        if institutionType.startswith("Public"):
            is_public = True

        grade_range = school.get("gradeRanges")

        if "K-" in grade_range:
            is_elementary = True
        if "-7" in grade_range or "-8" in grade_range:
            is_middle = True
        if "-12" in grade_range:
            is_high = True

        schools.append({
            "name": name,
            "is_elementary": is_elementary,
            "is_middle": is_middle,
            "is_high": is_high,
            "is_public": is_public,
            "rating": rating,
            "dist": distance_mi,
        })

    return schools


def get_price_history(data):
    price_history = []

    # get price history information (along with details)
    price_history_events = data.get("propertyHistoryInfo", {}).get("events") or []
    for event in price_history_events:
        # date
        ts = event.get("eventDate", 0)
        dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        date = dt.date().isoformat()

        # description
        description = event.get("eventDescription")

        # price
        price = event.get("price")
        if price is not None:
            price = price

        price_history.append({
            "date": date,
            "description": description,
            "price": price
        })

    return price_history


def get_covered_spaces(data):
    # drill down to the list of super-groups
    super_groups = data.get("amenitiesInfo", {}).get("superGroups") or []

    covered_value = None
    for sg in super_groups:
        for group in sg.get("amenityGroups") or []:
            # look through each amenity entry
            for entry in group.get("amenityEntries") or []:
                if entry.get("amenityName") == "Covered Spaces":
                    # grab the first (and only) value
                    covered_value = entry.get("amenityValues")[0] or None
                    break
            if covered_value is not None:
                break
        if covered_value is not None:
            break
    if covered_value is not None:
        covered_value = float(covered_value)
    return covered_value


def get_tax_annual(data):
    # drill down to the list of super-groups
    super_groups = data.get("amenitiesInfo", {}).get("superGroups") or []

    tax_annual = None
    for sg in super_groups:
        for group in sg.get("amenityGroups") or []:
            # look through each amenity entry
            for entry in group.get("amenityEntries") or []:
                if entry.get("amenityName") == "Tax Annual Amount":
                    # grab the first (and only) value
                    tax_annual = entry.get("amenityValues")[0] or None
                    break
            if tax_annual is not None:
                break
        if tax_annual is not None:
            break
    if tax_annual is not None:
        tax_annual = clean_price(tax_annual)
    return tax_annual


def get_agent_info(data):
    agent_name = data.get("amenitiesInfo", {}).get("mlsDisclaimerInfo", {}).get("listingAgentName")
    agent_broker = data.get("amenitiesInfo", {}).get("mlsDisclaimerInfo", {}).get("listingBrokerName")
    return ({'agent_name': agent_name,
             'agent_broker': agent_broker
             })
