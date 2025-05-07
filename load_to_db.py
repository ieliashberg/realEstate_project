# load_data.py

import json
from datetime import datetime

from sqlalchemy import select, exists
from sqlalchemy.exc import SQLAlchemyError
from dataBase import SessionLocal, School, Property, Price_History, Status_History, Listing, \
    Property_Change, Transaction, Property_School_Join
from sqlalchemy import inspect


def load_to_db(homes_json):
    session = SessionLocal()
    upsert_property(homes_json[0], session)


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
        unit_number=home.get('unitNumber', {}).get('value'),
        tax_annual_amount=home.get('tax_annual_amount'),
        hoa=home.get('hoa'),
        sqft=home.get('sqFt', {}).get('value'),
        covered_spaces=home.get('covered_spaces'),
        stories=home.get('stories')
    )

    try:
        old_prop = session.query(Property) \
            .filter_by(redfin_property_id=Property.redfin_property_id) \
            .first()
        if old_prop:
            mapper = inspect(old_prop.__class__)
            #  iterate through all column-based attributes
            for attr in mapper.attrs:
                # columnProperty attributes have .columns
                if hasattr(attr, 'columns'):
                    name = attr.key
                    old_val = getattr(old_prop, name)
                    new_val = getattr(new_prop, name)
                    if old_val != new_val:
                        session.add(Property_Change(
                            property_id=old_prop.property_id,
                            changed_attribute=name,
                            change_date=datetime.now(),
                            old_value=str(old_val),
                            new_value=str(new_val),
                            source="redfin",
                        ))

        else:
            session.add(new_prop)
            session.flush()     # gives newProperty.property_id
            print(f"Inserting new property (redfin_id={new_prop['redfin_property_id']}), property_id = {new_prop.property_id}")
            return new_prop.property_id
    except Exception as e:
        session.rollback()
        print("Error inserting property:", e)


def upsert_listing(home, propertyID, session):
    new_list = Listing(
        property_id=propertyID,
        redfin_listing_id=home.get('listingId'),
        list_date=home.get('list_date'),
        current_status=home.get('mlsStatus'),       # mls listing, ex: Active, closed, pending etc.)
        url=home.get('url'),
        agent_name=home.get('agent_name(s)'),
        broker=home.get('agent_broker(s)')
    )
    try:
        old_list = session.query(Listing)\
               .filter_by(redfin_listing_id=home['listingId'])\
               .first()

        if old_list:
            mapper = inspect(old_list.__class__)
            #  iterate through all column-based attributes
            for attr in mapper.attrs:
                # columnProperty attributes have .columns
                if hasattr(attr, 'columns'):
                    name = attr.key
                    old_val = getattr(old_list, name)
                    new_val = getattr(new_list, name)
                    if old_val != new_val:
                        session.add(Property_Change(
                            listing_id=old_list.listing_id,
                            changed_attribute=name,
                            change_date=datetime.now(),
                            old_value=str(old_val),
                            new_value=str(new_val),
                            source="redfin",
                        ))

        else:
            session.add(new_list)
            session.flush()  # gives newProperty.status_history_id
            print(
                f"Inserting new property (redfin_id={new_list['redfin_listing_id']}), status_history_id = {new_list.status_history_id}")
            return new_list.status_history_id
    except Exception as e:
        session.rollback()
        print("Error inserting property:", e)


def upsert_school(school_container, session):
    school = session.query(School).filter_by(name=school_container.get('name')).first()
    if not school:
        school = School(
            name=school_container['name'],
            rating=school_container.get('rating'),
            is_public=school_container.get('is_public'),
            is_elementary=school_container.get('is_elementary'),
            is_middle=school_container.get('is_middle'),
            is_high=school_container.get('is_high'),
            og_description=school_container.get('og_description')
        )
        session.add(school)
        session.flush()
    elif school.rating != school_container.get('rating'):
        school.rating = school.get('rating')
    return school.school_id


def upsert_property_school(property_id: int, school_id: int, dist: float, session):
    ps = session.query(Property_School_Join)\
                .filter_by(property_id=property_id, school_id=school_id)\
                .first()
    if not ps:
        ps = Property_School_Join(property_id=property_id, school_id=school_id, distance=dist)
        session.add(ps)
    elif ps.distance != dist:
        ps.distance = dist

