from ...database.connection import Property, Transaction, Listing, School, Price_History, Property_School_Join, Property_Change
from sqlalchemy.exc import NoResultFound
from datetime import datetime, timezone, timedelta
from ...utils.http import fetch_html_via_https, strip_json_beginning
from ...config.settings import REDFIN_HEADERS as redfin_base_headers
from bs4 import BeautifulSoup
import re
import json
import logging

# configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_url(payload: json):
    address = payload.get('address', '').replace(" ", "-").lower()
    city = payload.get('city', '').replace(" ", "-").lower()
    state = payload.get('state', '').upper()
    zipcode = payload.get('zip', '') or payload.get('zipcode', '')
    redfin_id = payload.get('redfin_property_id', '')
    url = f"https://www.redfin.com/{state}/{city}/{address}-{zipcode}/home/{redfin_id}"
    return url


def get_specific_property_info(payload: json):
    # Use the original Redfin URL if available, otherwise fall back to creating one
    url = payload.get('url')
    if url:
        # The URL from Redfin is relative, so we need to add the base URL
        if url.startswith('/'):
            url = f"https://www.redfin.com{url}"
    else:
        # Fallback to the old create_url method for backward compatibility
        url = create_url(payload)
    
    extra_info = None
    try:
        html = fetch_html_via_https(url, redfin_base_headers)
        if not html:
            raise RuntimeError(f"Failed to fetch HTML from {url}")

        data = get_property_json(html)
        
        # Check if we have amenitiesInfo in the data
        if data and 'amenitiesInfo' in data:
            # We have the detailed amenities data
            agent_info = get_agent_info(data)
            extra_info = {
                "schools": get_schools(data),
                "price_history": get_price_history(data),
                "covered_spaces": get_covered_spaces(data),
                "tax_annual_amount": get_tax_annual(data),
                "agents_name": agent_info.get('agent_name'),
                "agents_broker": agent_info.get('agent_broker'),
            }
        else:
            # Try to look for the belowTheFold data in the HTML
            # This data might be in a separate script tag or API response
            below_the_fold_data = _extract_below_the_fold_data(html)
            if below_the_fold_data and 'amenitiesInfo' in below_the_fold_data:
                # We found the amenities data in the belowTheFold response
                agent_info = get_agent_info(below_the_fold_data)
                extra_info = {
                    "schools": get_schools(below_the_fold_data),
                    "price_history": get_price_history(below_the_fold_data),
                    "covered_spaces": get_covered_spaces(below_the_fold_data),
                    "tax_annual_amount": get_tax_annual(below_the_fold_data),
                    "agents_name": agent_info.get('agent_name'),
                    "agents_broker": agent_info.get('agent_broker'),
                }
            else:
                # No detailed info available
                extra_info = {
                    "schools": [],
                    "price_history": [],
                    "covered_spaces": None,
                    "tax_annual_amount": None,
                    "agents_name": None,
                    "agents_broker": None,
                }

    except Exception as e:
        logger.error(f"[ERROR] processing {url} raised {type(e).__name__}: {e}")

    return extra_info


def _extract_below_the_fold_data(html):
    """Extract belowTheFold data from Redfin HTML which contains amenitiesInfo."""
    
    soup = BeautifulSoup(html, "html.parser")
    script_tags = soup.find_all("script")
    
    for script in script_tags:
        text = script.get_text()
        
        # Look for the belowTheFold API response in the script
        if "belowTheFold" in text and "amenitiesInfo" in text:
            # Try to find the belowTheFold data in the reactServerState
            if "root.__reactServerState" in text:
                # Look for the belowTheFold entry in the data cache
                below_the_fold_match = re.search(
                    r"root\.__reactServerState\.InitialContext\s*=\s*({.*?});",
                    text,
                    flags=re.DOTALL
                )
                if below_the_fold_match:
                    try:
                        context_data = json.loads(below_the_fold_match.group(1))
                        data_cache = context_data.get('ReactServerAgent.cache', {}).get('dataCache', {})
                        
                        # Look for the belowTheFold entry
                        below_the_fold_key = '/stingray/api/home/details/belowTheFold'
                        if below_the_fold_key in data_cache:
                            entry = data_cache[below_the_fold_key]
                            if 'res' in entry and 'text' in entry['res']:
                                response_text = entry['res']['text']
                                
                                # The response text starts with {}&&, so we need to strip it
                                if response_text.startswith('{}&&'):
                                    json_text = strip_json_beginning(response_text, '{}&&')
                                    response_data = json.loads(json_text)
                                    
                                    # Extract the payload from the response
                                    if 'payload' in response_data:
                                        return response_data['payload']
                                    elif 'result' in response_data:
                                        return response_data['result']
                                    else:
                                        return response_data
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue
    
    return None


def upsert_more_info(session, extra_info: json, propertyID, listingID, isNewProperty):
    if extra_info is None:
        return
    
    # fetch property to update
    try:
        prop = session.query(Property).filter_by(property_id=propertyID).one()
    except NoResultFound:
        raise RuntimeError(f"Property {propertyID} not found")

    # update necessary info for property
    cv = extra_info.get("covered_spaces")
    if cv is not None:
        try:
            current_covered_spaces = prop.covered_spaces
            cv = int(float(cv))
            if current_covered_spaces is not None:
                if cv is not None and current_covered_spaces != cv:
                    session.add(Property_Change(
                        property_id=prop.property_id,
                        changed_attribute="covered_spaces",
                        change_date=datetime.now(timezone.utc),
                        old_value=str(current_covered_spaces),
                        new_value=str(cv),
                        source="redfin",
                    ))
                    setattr(prop, "covered_spaces", cv)
                    logger.info(f"DATABASE UPDATE: Property {propertyID} - Covered spaces changed from {current_covered_spaces} to {cv}")
                    logger.info(f"DATABASE INSERT: Property {propertyID} - Created Property_Change record for covered_spaces")
            else:
                prop.covered_spaces = cv
                logger.info(f"DATABASE ADD: Property {propertyID} - Added covered spaces: {cv}")
        except (TypeError, ValueError):
            prop.covered_spaces = None

    tx = extra_info.get("tax_annual_amount")
    if tx is not None:
        try:
            current_tax_amount = prop.tax_annual_amount
            tx = int(float(tx))
            if current_tax_amount is not None:
                if tx is not None and current_tax_amount != tx:
                    session.add(Property_Change(
                        property_id=prop.property_id,
                        changed_attribute="tax_annual_amount",
                        change_date=datetime.now(timezone.utc),
                        old_value=str(current_tax_amount),
                        new_value=str(tx),
                        source="redfin",
                    ))
                    setattr(prop, "tax_annual_amount", tx)
                    logger.info(f"DATABASE UPDATE: Property {propertyID} - Tax annual amount changed from ${current_tax_amount:,} to ${tx:,}")
                    logger.info(f"DATABASE INSERT: Property {propertyID} - Created Property_Change record for tax_annual_amount")
            else:
                prop.tax_annual_amount = tx
                logger.info(f"DATABASE ADD: Property {propertyID} - Added tax annual amount: ${tx:,}")
        except (TypeError, ValueError):
            prop.covered_spaces = None
    session.flush()

    # fetch & update Listing
    try:
        lst = session.query(Listing).filter_by(listing_id=listingID).one()
    except NoResultFound:
        raise RuntimeError(f"Listing {listingID} not found")

    new_agent_name = extra_info.get("agents_name")
    old_agent_name = lst.agent_name
    if new_agent_name is not None:
        if old_agent_name is not None:
            if old_agent_name != new_agent_name:
                lst.agent_name = new_agent_name
                logger.info(f"DATABASE UPDATE: Listing {listingID} - Agent name changed from '{old_agent_name}' to '{new_agent_name}'")
        else:
            lst.agent_name = new_agent_name
            logger.info(f"DATABASE ADD: Listing {listingID} - Added agent name: '{new_agent_name}'")

    new_broker = extra_info.get("agents_broker")
    old_broker = lst.broker
    if new_broker is not None:
        if old_broker is not None:
            if  old_broker != new_broker:
                lst.broker = new_broker
                logger.info(f"DATABASE UPDATE: Listing {listingID} - Broker changed from '{old_broker}' to '{new_broker}'")
        else:
            lst.broker = new_broker
            logger.info(f"DATABASE ADD: Listing {listingID} - Added broker: '{new_broker}'")

    session.flush()

    # upsert schools & joins
    for school in extra_info.get("schools", []):
        school_id = upsert_school(school, session)
        upsert_property_school(propertyID, school_id, school, session)
    session.flush()

    # bootstrap sold‐transaction history
    #    We only pass the list of events; bootstrap_sold_histories
    #    will skip non-sold markers and avoid duplicates if you've written it that way.
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
        # Find the most recent "Sold" event
        most_recent_sold_index = -1
        for i, entry in enumerate(price_history):
            description = entry.get("description", "")
            if "Sold" in description:
                most_recent_sold_index = i

        # Only consider entries after the most recent sold event
        if most_recent_sold_index == -1:
            relevant_entries = price_history
        else:
            relevant_entries = price_history[most_recent_sold_index + 1:]

        # Use all relevant entries (not just recent ones for bootstrap)
        recent_entries = relevant_entries

        # Sort entries by date (oldest first)
        recent_entries.sort(key=lambda x: datetime.strptime(x.get("date"), "%Y-%m-%d"))

        # Deduplicate same-day events by keeping only the most recent one (closest to top of original list)
        unique_entries = []
        seen_dates = set()
        for entry in reversed(recent_entries):
            entry_date = entry.get("date")
            if entry_date not in seen_dates:
                unique_entries.append(entry)
                seen_dates.add(entry_date)
        unique_entries.reverse()

        # Filter out rental-related events
        filtered_entries = []
        for entry in unique_entries:
            description = entry.get("description", "").lower()
            if "rent" in description or "rental" in description:
                continue
            filtered_entries.append(entry)

        # Find the first listing event ("Listed (Active)" or "Listed")
        initial_event = None
        for entry in filtered_entries:
            description = entry.get("description", "")
            if description in ["Listed (Active)", "Listed"]:
                initial_event = entry
                break

        if not initial_event:
            session.flush()
            logger.warning(f"No valid listing event found for listing {listing_id} (last 5 months)")
            return

        # Collect all price change and listing events in order
        events_to_chain = []
        for entry in filtered_entries:
            description = entry.get("description", "")
            if description in ["Listed (Active)", "Listed", "Price Changed"]:
                events_to_chain.append(entry)

        if not events_to_chain:
            session.flush()
            logger.warning(f"No price events to chain for listing {listing_id} (last 5 months)")
            return

        # Chain transitions: null -> first listed, then each price change/relist only if price changes
        prev_price = None
        for idx, entry in enumerate(events_to_chain):
            this_price = entry.get('price')
            this_date = entry.get('date')
            if idx == 0:
                # First event: null -> first listed price
                session.add(Price_History(
                    listing_id=listing_id,
                    change_date=this_date,
                    old_price=None,
                    new_price=this_price,
                    source="redfin"
                ))
                logger.info(f"DATABASE INSERT: Price History - Listing {listing_id} - Initial price: ${this_price:,} on {this_date}")
                prev_price = this_price
            else:
                # Only add if price actually changes
                if prev_price != this_price:
                    session.add(Price_History(
                        listing_id=listing_id,
                        change_date=this_date,
                        old_price=prev_price,
                        new_price=this_price,
                        source="redfin"
                    ))
                    logger.info(f"DATABASE INSERT: Price History - Listing {listing_id} - Price changed from ${prev_price:,} to ${this_price:,} on {this_date}")
                    prev_price = this_price
        session.flush()
        logger.info(f"Finished bootstrapping price history for listing {listing_id} (last 5 months)")
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
            session.flush()
            logger.info(f"DATABASE INSERT: Property-School Join - Property {property_id} → School {school_id} (Distance: {dist})")
        else:
            old_dist = old_prop_school.distance
            if dist is not None and float(old_dist) != float(dist):
                old_prop_school.distance = dist
                old_prop_school.last_updated = datetime.now(timezone.utc)
                session.flush()
                logger.info(f"DATABASE UPDATE: Property-School Join - Property {property_id} → School {school_id} - Distance changed from {old_dist} to {dist}")

    except Exception:
        logger.exception(f"Error upserting property_school with school_id={school_id}, property_id={property_id}")
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
            logger.info(f"DATABASE INSERT: Transaction - Property {property_id} - {description} for ${entry.get('price'):,} on {dt}")

            # remember this date for next loop
            last_sale_date = dt

        session.flush()
        logger.info(f"Finished bootstrapping sold history for property {property_id}")
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
    new_rating = school.get("rating")
    if not existing:
        new_school = School(
            name=school.get('name'),
            rating=new_rating,
            is_public=school.get('is_public'),
            is_elementary=school.get('is_elementary'),
            is_middle=school.get('is_middle'),
            is_high=school.get('is_high'),
        )
        session.add(new_school)
        session.flush()  # populates new_school.school_id
        logger.info(f"DATABASE INSERT: School '{new_school.name}' (ID: {new_school.school_id}) - Rating: {new_rating}")
        return new_school.school_id
    else:
        # update if needed
        old_rating = existing.rating
        if new_rating is not None and old_rating != new_rating:
            existing.rating = new_rating
            logger.info(f"DATABASE UPDATE: School '{existing.name}' (ID: {existing.school_id}) - Rating changed from {old_rating} to {new_rating}")
            session.flush()

        return existing.school_id


def get_property_json(html):
    
    soup = BeautifulSoup(html, "html.parser")
    # Check all script tags, not just those with type="text/javascript"
    script_tags = soup.find_all("script")
    if not script_tags:
        raise ValueError("No script tags found in HTML")
    
    # First, try the old pattern (window.__INITIAL_STATE__)
    for script in script_tags:
        text = script.get_text()
        if "window.__INITIAL_STATE__" in text:
            m = re.search(
                r"window\.__INITIAL_STATE__\s*=\s*({.*?})\s*;\s*$",
                text,
                flags=re.DOTALL
            )
            if not m:
                raise ValueError("Found the script tag, but regex didn't match.")
            payload = m.group(1)
            payload = re.sub(r':\s*undefined', ':null', payload)
            payload = re.sub(r',\s*([}\]])', r'\1', payload)
            return json.loads(payload)
    
    # If old pattern not found, try the new pattern (root.__reactServerState)
    for script in script_tags:
        text = script.get_text()
        if "root.__reactServerState" in text:
            # Look for the InitialContext assignment
            m = re.search(
                r"root\.__reactServerState\.InitialContext\s*=\s*({.*?});",
                text,
                flags=re.DOTALL
            )
            if m:
                try:
                    context_data = json.loads(m.group(1))
                    data_cache = context_data.get('ReactServerAgent.cache', {}).get('dataCache', {})
                    
                    # Look for the aboveTheFold entry which contains property data
                    above_the_fold_key = '/stingray/api/home/details/aboveTheFold'
                    if above_the_fold_key in data_cache:
                        entry = data_cache[above_the_fold_key]
                        if 'res' in entry and 'text' in entry['res']:
                            response_text = entry['res']['text']
                            
                            # The response text starts with {}&&, so we need to strip it
                            if response_text.startswith('{}&&'):
                                json_text = strip_json_beginning(response_text, '{}&&')
                                response_data = json.loads(json_text)
                                
                                # Extract the payload from the response
                                if 'payload' in response_data:
                                    return response_data['payload']
                                elif 'result' in response_data:
                                    return response_data['result']
                                else:
                                    return response_data
                    
                    # If aboveTheFold not found, try other property-related entries
                    for key in data_cache.keys():
                        if any(prop in key for prop in ['property', 'listing', 'home', 'details']):
                            entry = data_cache[key]
                            if 'res' in entry and 'text' in entry['res']:
                                response_text = entry['res']['text']
                                if response_text.startswith('{}&&'):
                                    try:
                                        json_text = strip_json_beginning(response_text, '{}&&')
                                        response_data = json.loads(json_text)
                                        if 'payload' in response_data:
                                            return response_data['payload']
                                    except:
                                        continue
                        
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    # Continue to next script if this one fails
                    continue
    
    raise ValueError("Could not find any <script> with window.__INITIAL_STATE__ or root.__reactServerState")


def clean_price(input_str: str):
    if input_str is None or input_str == "":
        return None
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
