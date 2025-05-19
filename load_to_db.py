import json
import traceback
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, exists
from sqlalchemy.exc import SQLAlchemyError
from dataBase import SessionLocal, School, Property, Price_History, Status_History, Listing, \
    Property_Change, Transaction, Property_School_Join
from sqlalchemy import inspect, desc


def load_to_db(homes_json):
    session = SessionLocal()
    try:
        for home in homes_json:
            prop_id = upsert_property(home, session)
            upsert_listing(home, prop_id, session)

            for school in home.get('schools', []):
                school_id = upsert_school(school, session)
                # note the correct order: property_id, school_id, then dist, then session
                upsert_property_school(
                    prop_id, school_id, school, session
                )

        session.commit()
    except Exception as e:
        print("Exception occurred in parsing/loading to database:", e)
        session.rollback()
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
            print(f"Inserting new property and corresponding transaction table (redfin_id={new_prop.redfin_property_id}), property_id = {new_prop.property_id}")

            return new_prop.property_id
    except Exception as e:
        print("Error inserting property:", e)
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
        print("Error bootstrapping sold histories")
        raise


def upsert_listing(home, propertyID, session):
    new_list = Listing(
        property_id=propertyID,
        redfin_listing_id=home.get('listingId'),
        list_date=home.get('list_date'),
        current_status=home.get('mlsStatus'),       # mls listing, ex: Active, closed, pending etc.)
        url=home.get('url'),
        agent_name=home.get('agent_names'),
        broker=home.get('agent_brokers'),
        isNewConstruction=home.get('isNewConstruction'),
        current_price=home.get('price', {}).get('value')
    )
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
            print(
                f"Inserting new listing and bootstrapping corresponding price_history table (redfin_id={new_list.redfin_listing_id})")
            return new_list.listing_id
    except Exception as e:
        session.rollback()
        print("Error inserting listing:", e)
        raise


def bootstrap_price_histories(listing_id, home, session):
    try:
        ph = home.get("price_history", [])
        slice_entries = []
        for entry in ph:
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
        print("Finished bootstrapping price history")
        return
    except Exception:
        print("Error bootstrapping price histories")
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

    except Exception:
        print("Error upserting property_school")
        session.rollback()
        raise




