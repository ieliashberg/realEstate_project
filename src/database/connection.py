"""
Database connection and session management.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base
import os

# Database configuration - default to PostgreSQL
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://ilan@localhost:5432/real_estate')

# Create engine
engine = create_engine(DATABASE_URL, echo=False)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Import all models for easy access
from .models import (
    Property,
    Listing,
    School,
    PriceHistory as Price_History,
    Transaction,
    PropertySchool as Property_School_Join,
    PropertyChange as Property_Change,
    ZestimateHistory as Zestimate_History,
    Zipcodes,
    PiplineTables as Pipline_Tables,
    StatusHistory as Status_History,
    UserAgent
)

__all__ = [
    'engine',
    'SessionLocal', 
    'Base',
    'Property',
    'Listing',
    'School',
    'Price_History',
    'Transaction',
    'Property_School_Join',
    'Property_Change',
    'Zestimate_History',
    'Zipcodes',
    'Pipline_Tables',
    'Status_History',
    'UserAgent'
]
