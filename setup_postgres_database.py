#!/usr/bin/env python3
"""
Setup script for PostgreSQL database with all required tables.
"""

import os
import sys
from sqlalchemy import create_engine, text
from src.database.connection import engine, Base, SessionLocal
from src.database.models import Zipcodes
from datetime import datetime, timezone, timedelta

def create_database():
    """Create the database if it doesn't exist."""
    # Get database URL without the database name
    db_url = os.getenv('DATABASE_URL', 'postgresql://ilan@localhost:5432/real_estate')
    if '/' in db_url:
        base_url = db_url.rsplit('/', 1)[0]
        db_name = db_url.rsplit('/', 1)[1]
    else:
        base_url = 'postgresql://ilan@localhost:5432'
        db_name = 'real_estate'
    
    # Connect to postgres database to create the target database
    admin_engine = create_engine(base_url + '/postgres', isolation_level='AUTOCOMMIT')
    
    with admin_engine.connect() as conn:
        # Check if database exists
        result = conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'"))
        if not result.fetchone():
            print(f"Creating database '{db_name}'...")
            conn.execute(text(f"CREATE DATABASE {db_name}"))
            print(f"Database '{db_name}' created successfully.")
        else:
            print(f"Database '{db_name}' already exists.")

def create_tables():
    """Create all tables in the database."""
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("All tables created successfully.")

def add_sample_data():
    """Add sample data for testing."""
    session = SessionLocal()
    try:
        # Add a sample zipcode
        existing_zipcode = session.query(Zipcodes).filter_by(zipcode="85297").first()
        if not existing_zipcode:
            sample_zipcode = Zipcodes(
                zipcode="85297",
                for_sale_fetch_frequency_days=1,
                sold_fetch_frequency_days=7,
                last_for_sale_fetch=datetime.now(timezone.utc),
                last_sold_fetch=datetime.now(timezone.utc)
            )
            session.add(sample_zipcode)
            session.commit()
            print("✅ Added sample zipcode 85297")
        else:
            print("✅ Sample zipcode 85297 already exists")
            
    except Exception as e:
        print(f"Could not add sample data: {e}")
        session.rollback()
    finally:
        session.close()

def main():
    """Main setup function."""
    print("Setting up PostgreSQL database for real estate project...")
    
    try:
        # Create database
        create_database()
        
        # Create tables
        create_tables()
        
        # Add sample data
        add_sample_data()
        
        print("\nDatabase setup completed successfully!")
        print("\nTo use the database, set the DATABASE_URL environment variable:")
        print("export DATABASE_URL='postgresql://ilan@localhost:5432/real_estate'")
        
    except Exception as e:
        print(f"Database setup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
