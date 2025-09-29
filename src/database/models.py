"""
SQLAlchemy models for the real estate database.
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, Float, DateTime, Numeric, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

Base = declarative_base()


class Property(Base):
    """Property table model."""
    __tablename__ = 'property'
    
    property_id = Column(Integer, primary_key=True, autoincrement=True)
    redfin_property_id = Column(Integer, unique=True, nullable=False)
    address = Column(Text, nullable=False)
    city = Column(Text, nullable=False)
    state = Column(String(2), nullable=False)
    zip = Column(String(10), nullable=False)
    latitude = Column(Float)
    longitude = Column(Float)
    lot_size = Column(Integer)
    year_built = Column(Integer)
    property_type = Column(Integer)
    beds = Column(Integer)
    baths = Column(Float)
    sqft = Column(Integer)
    covered_spaces = Column(Integer)
    stories = Column(Float)
    unit_number = Column(Text)
    tax_annual_amount = Column(Integer)
    hoa = Column(Integer)
    builder_name = Column(Text)
    is_on_market = Column(Boolean)
    
    # Relationships
    listings = relationship("Listing", back_populates="property")
    property_changes = relationship("PropertyChange", back_populates="property")
    transactions = relationship("Transaction", back_populates="property")
    property_schools = relationship("PropertySchool", back_populates="property")


class Listing(Base):
    """Listing table model."""
    __tablename__ = 'listing'
    
    listing_id = Column(Integer, primary_key=True, autoincrement=True)
    property_id = Column(Integer, ForeignKey('property.property_id'), nullable=False)
    redfin_listing_id = Column(Integer, unique=True)
    list_date = Column(DateTime)
    current_status = Column(String(50))
    url = Column(Text)
    agent_name = Column(Text)
    broker = Column(Text)
    isnewconstruction = Column(Boolean)
    curr_price = Column(Integer)
    
    # Relationships
    property = relationship("Property", back_populates="listings")
    price_histories = relationship("PriceHistory", back_populates="listing")
    status_histories = relationship("StatusHistory", back_populates="listing")


class School(Base):
    """School table model."""
    __tablename__ = 'school'
    
    school_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    rating = Column(Numeric(3, 1))
    is_public = Column(Boolean)
    is_elementary = Column(Boolean)
    is_middle = Column(Boolean)
    is_high = Column(Boolean)
    og_description = Column(Text)
    
    # Relationships
    property_schools = relationship("PropertySchool", back_populates="school")


class PropertySchool(Base):
    """Property-School junction table model."""
    __tablename__ = 'property_school'
    
    property_id = Column(Integer, ForeignKey('property.property_id'), primary_key=True)
    school_id = Column(Integer, ForeignKey('school.school_id'), primary_key=True)
    distance = Column(Numeric(6, 2))
    
    # Relationships
    property = relationship("Property", back_populates="property_schools")
    school = relationship("School", back_populates="property_schools")


class PriceHistory(Base):
    """Price history table model."""
    __tablename__ = 'price_history'
    
    price_history_id = Column(Integer, primary_key=True, autoincrement=True)
    listing_id = Column(Integer, ForeignKey('listing.listing_id'), nullable=False)
    change_date = Column(DateTime)
    old_price = Column(Numeric(12, 2))
    new_price = Column(Numeric(12, 2))
    source = Column(Text)
    
    # Relationships
    listing = relationship("Listing", back_populates="price_histories")


class PropertyChange(Base):
    """Property change table model."""
    __tablename__ = 'property_change'
    
    change_id = Column(Integer, primary_key=True, autoincrement=True)
    property_id = Column(Integer, ForeignKey('property.property_id'), nullable=False)
    changed_attribute = Column(Text)
    change_date = Column(DateTime)
    old_value = Column(Text)
    new_value = Column(Text)
    source = Column(Text)
    
    # Relationships
    property = relationship("Property", back_populates="property_changes")


class StatusHistory(Base):
    """Status history table model."""
    __tablename__ = 'status_history'
    
    status_history_id = Column(Integer, primary_key=True, autoincrement=True)
    listing_id = Column(Integer, ForeignKey('listing.listing_id'), nullable=False)
    change_date = Column(DateTime)
    old_status = Column(String(50))
    new_status = Column(String(50))
    source = Column(Text)
    
    # Relationships
    listing = relationship("Listing", back_populates="status_histories")


class Transaction(Base):
    """Transaction table model."""
    __tablename__ = 'transaction'
    
    transaction_id = Column(Integer, primary_key=True, autoincrement=True)
    property_id = Column(Integer, ForeignKey('property.property_id'), nullable=False)
    transaction_date = Column(DateTime)
    transaction_type = Column(String(50))
    price = Column(Numeric(12, 2))
    
    # Relationships
    property = relationship("Property", back_populates="transactions")


class Zipcodes(Base):
    """Zipcodes table model - not in original schema but needed for the application."""
    __tablename__ = 'zipcodes'
    
    zipcode_id = Column(Integer, primary_key=True, autoincrement=True)
    zipcode = Column(String(10), unique=True, nullable=False)
    last_for_sale_fetch = Column(DateTime)
    last_sold_fetch = Column(DateTime)
    for_sale_fetch_frequency_days = Column(Integer, default=1)
    sold_fetch_frequency_days = Column(Integer, default=7)
    for_sale_request_url = Column(Text)
    sold_request_url = Column(Text)


class SimpleTest(Base):
    """Simple test table model."""
    __tablename__ = 'simple_test'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text)
    value = Column(Integer)


# Additional tables that might be needed based on the connection.py file
class ZestimateHistory(Base):
    """Zestimate history table model."""
    __tablename__ = 'zestimate_history'
    
    zestimate_history_id = Column(Integer, primary_key=True, autoincrement=True)
    property_id = Column(Integer, ForeignKey('property.property_id'), nullable=False)
    change_date = Column(DateTime)
    old_zestimate = Column(Numeric(12, 2))
    new_zestimate = Column(Numeric(12, 2))
    source = Column(Text)
    
    # Relationships
    property = relationship("Property")


class PiplineTables(Base):
    """Pipeline tables model."""
    __tablename__ = 'pipline_tables'
    
    job_id = Column(Integer, primary_key=True, autoincrement=True)
    job_type = Column(String(100), nullable=False)
    payload = Column(Text)
    status = Column(String(50), default='pending')
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    error_message = Column(Text)


class UserAgent(Base):
    """User Agent model for web scraping."""
    __tablename__ = 'user_agents'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_agent = Column(Text, nullable=False, unique=True)
    status = Column(String(20), default='unknown')  # working, failing, retired, unknown
    fail_count = Column(Integer, default=0)
    last_tested = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))