# FILE NOT CURRENTLY USED
from datetime import datetime, timezone, timedelta
from dataBase import SessionLocal, School, Property, Price_History, Status_History, Listing, \
    Property_Change, Transaction, Property_School_Join
from sqlalchemy import inspect
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_to_db(homes_json):
    for home in homes_json:
        session = SessionLocal()
        try:
            # upsert the property + related tables
            prop_id = upsert_property(home, session)

            # upsert the listing
            upsert_listing(home, prop_id, session)

            # upsert schools
            for school in home.get('schools', []):
                school_id = upsert_school(school, session)
                upsert_property_school(prop_id, school_id, school, session)

            # commit this property's transaction
            session.commit()
            logger.info(f"Successfully loaded property {home.get('propertyId')}")

        except Exception as e:
            # rollback only the current session
            session.rollback()
            logger.exception(f"Failed to load property {home.get('propertyId')}: {e}")

        finally:
            session.close()


def upsert_property(home, session):
    new_prop = Property(  # .get everywhere gives us safe retrieval in case doesn't exist
        redfin_property_id=home.get('propertyId'),
        address=home.get('streetLine', {}).get('value'),
        city=home.get('city'),
        state=home.get('state'),
        zip=home.get('zip'),
        latitude=home.get('latLong', {}).get('value', {}).get('latitude'),
        longitude=home.get('latLong', {}).get('value', {}).get('longitude'),
        lot_size=home.get('lotSize', {}).get('value'),
        year_built=home.get('yearBuilt', {}).get('value'),
        property_type=home.get('uiPropertyType'),  # ex: home, condo, townhouse, multifamily, land, mobile
        beds=home.get('beds'),
        baths=home.get('baths'),
        sqft=home.get('sqFt', {}).get('value'),
        covered_spaces=home.get('covered_spaces'),
        stories=home.get('stories'),
        unit_number=home.get('unitNumber', {}).get('value'),
        tax_annual_amount=home.get('tax_annual_amount'),
        hoa=home.get('hoa', {}).get('value'),
        builder_name=home.get('newConstructionCommunityInfo', {}).get('builderName'),
        is_on_market=(home.get('mlsStatus') != "Closed" and home.get('mlsStatus') != "Sold"),
        current_zestimate=home.get('zestimate'),
        current_zestimate_low=home.get('zestimate_low'),
        current_zestimate_high=home.get('zestimate_high')
    )

    try:
        old_prop = session.query(Property) \
            .filter_by(redfin_property_id=new_prop.redfin_property_id) \
            .first()
        if old_prop:
            prop_id = None
            skip_fields = {
                "current_zestimate",
                "current_zestimate_low",
                "current_zestimate_high",
            }
            mapper = inspect(old_prop.__class__)
            #  iterate through all column-based attributes
            for attr in mapper.attrs:
                # columnProperty attributes have .columns
                if hasattr(attr, 'columns'):
                    col = attr.columns[0]
                    if col.primary_key:
                        prop_id = getattr(old_prop, attr.key)
                        continue  # skip pk field
                    name = attr.key
                    if name in skip_fields:
                        continue
                    old_val = getattr(old_prop, name)
                    new_val = getattr(new_prop, name)
                    if old_val != new_val:
                        session.add(Property_Change(
                            property_id=old_prop.property_id,
                            changed_attribute=name,
                            change_date=datetime.now(timezone.utc),
                            old_value=str(old_val),
                            new_value=str(new_val),
                            source="redfin",
                        ))
                        setattr(old_prop, name, new_val)

            # if it was on the market before and now current mlsStatus is "sold"
            if old_prop.is_on_market and home.get('mlsStatus') == "Sold":
                # update the transaction table
                session.add(Transaction(
                    property_id=old_prop.property_id,
                    transaction_date=datetime.fromtimestamp(home.get('soldDate')/1000, tz=timezone.utc),
                    transaction_type="Sold",
                    price=home.get('price', {}).get('value')
                ))
            return old_prop.property_id

        else:
            session.add(new_prop)
            session.flush()     # gives newProperty.property_id

            # bootstrap sold histories in transaction table
            bootstrap_sold_histories(new_prop.property_id, home, session)

            session.flush()     # gives the transaction table its transactionId
            logger.info(f"Inserting new property and corresponding transaction table (redfin_id={new_prop.redfin_property_id}), property_id = {new_prop.property_id}")

            return new_prop.property_id
    except Exception as e:
        logger.exception("Error inserting property:", e)
        session.rollback()
        raise


def bootstrap_sold_histories(property_id, home, session):
    sold_markers = (
        "Sold (Public Records)",
        "Sold (MLS)",
        "Sold (MLS) (Closed)",
        "Sold (MLS) (Sold)",
    )

    try:
        last_sale_date = None

        for entry in home.get('price_history'):
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
    except Exception:
        logger.exception("Error bootstrapping sold histories")
        raise


def upsert_listing(home, propertyID, session):
    new_list = Listing(
        property_id=propertyID,
        redfin_listing_id=home.get('listingId'),
        list_date=home.get('list_date'),
        current_status=home.get('mlsStatus'),       # mls listing, ex: Active, closed, pending etc.)
        url=home.get('url'),
        agent_name=home.get('agent_name'),
        broker=home.get('agent_broker'),
        isNewConstruction=home.get('isNewConstruction'),
        current_price=home.get('price', {}).get('value')
    )

    # if listing id doesn't exist, skip over making a listing
    if new_list.redfin_listing_id is None:
        logger.info("Error Upserting listing, No redfin listing id")
        return
    try:
        old_list = session.query(Listing)\
               .filter_by(redfin_listing_id=home['listingId'])\
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
            return old_list.listing_id

        else:
            session.add(new_list)
            session.flush()  # gives new_listing.listing_id

            bootstrap_price_histories(new_list.listing_id, home, session)
            logger.info(
                f"Inserting new listing and bootstrapping corresponding price_history table (redfin_id={new_list.redfin_listing_id})")
            return new_list.listing_id
    except Exception as e:
        session.rollback()
        logger.exception("Error inserting listing:", e)
        raise


def bootstrap_price_histories(listing_id, home, session):
    try:
        ph = home.get("price_history", [])
        
        # Find the most recent "Sold" event
        most_recent_sold_index = -1
        for i, entry in enumerate(ph):
            description = entry.get("description", "")
            if "Sold" in description:
                most_recent_sold_index = i
        
        # If no sold event found, use all entries
        if most_recent_sold_index == -1:
            relevant_entries = ph
        else:
            # Get entries after the most recent sold event
            relevant_entries = ph[most_recent_sold_index + 1:]
        
        # Filter to only entries within the last 5 months
        five_months_ago = datetime.now() - timedelta(days=150)  # ~5 months
        recent_entries = []
        
        for entry in relevant_entries:
            try:
                entry_date = datetime.strptime(entry.get("date"), "%Y-%m-%d")
                if entry_date >= five_months_ago:
                    recent_entries.append(entry)
            except (ValueError, TypeError):
                # Skip entries with invalid dates
                continue
        
        # Sort entries by date (oldest first)
        recent_entries.sort(key=lambda x: datetime.strptime(x.get("date"), "%Y-%m-%d"))
        
        # Find the initial listing price (first "Listed (Active)" or "Listed" in recent entries)
        initial_price = None
        for entry in recent_entries:
            description = entry.get("description", "")
            if description in ["Listed (Active)", "Listed"]:
                initial_price = entry.get('price')
                break
        
        # Extract all price changes and listing events in chronological order
        price_events = []
        for entry in recent_entries:
            description = entry.get("description", "")
            if description in ["Price Changed", "Listed (Active)", "Listed"]:
                price_events.append(entry)
        
        # Create price history records
        prev_price = initial_price
        for entry in price_events:
            description = entry.get("description", "")
            this_price = entry.get('price')
            
            # Skip if this is the initial listing and we already have a price
            if description in ["Listed (Active)", "Listed"] and prev_price is None:
                prev_price = this_price
                continue
            
            # Create price history record
            if prev_price is not None and this_price is not None:
                session.add(Price_History(
                    listing_id=listing_id,
                    change_date=entry.get("date"),
                    old_price=prev_price,
                    new_price=this_price,
                    source="redfin"
                ))
            
            prev_price = this_price
        
        session.flush()
        logger.info(f"Finished bootstrapping price history for listing {listing_id} (last 5 months)")
        return
    except Exception:
        logger.exception("Error bootstrapping price histories")
        session.rollback()
        raise


def upsert_school(school_container, session) -> int:
    """
    Insert or update a School and always return its school_id.
    """
    existing = (
        session
        .query(School)
        .filter_by(name=school_container['name'])
        .first()
    )
    if not existing:
        new_school = School(
            name=school_container.get('name'),
            rating=school_container.get('rating'),
            is_public=school_container.get('is_public'),
            is_elementary=school_container.get('is_elementary'),
            is_middle=school_container.get('is_middle'),
            is_high=school_container.get('is_high'),
        )
        session.add(new_school)
        session.flush()  # populates new_school.school_id
        return new_school.school_id
    else:
        # update if needed
        updated = False
        if existing.rating != school_container.get('rating'):
            existing.rating = school_container.get('rating')
            updated = True
        if updated:
            session.flush()
        return existing.school_id


def upsert_property_school(property_id: int, school_id: int, school, session):
    dist = school.get('dist')
    new_prop_school = Property_School_Join(
        property_id=property_id,
        school_id=school_id,
        distance=dist
    )
    try:
        old_prop_school = session.query(Property_School_Join)\
                    .filter_by(property_id=property_id, school_id=school_id)\
                    .first()
        if not old_prop_school:
            session.add(new_prop_school)

        elif old_prop_school.distance != dist:
            old_prop_school.distance = dist
            old_prop_school.last_updated = datetime.now()

    except Exception:
        logger.exception("Error upserting property_school")
        session.rollback()
        raise
