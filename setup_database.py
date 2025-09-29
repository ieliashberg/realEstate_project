#!/usr/bin/env python3
"""
Database setup script for the Real Estate Data Pipeline.
Creates essential tables for the system to function.
"""

import sys
import os
from sqlalchemy import create_engine, text
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import sessionmaker

# Add the project directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.database.connection import engine, SessionLocal

def create_essential_tables():
    """Create essential tables for the system to function."""
    
    # SQL for creating essential tables (SQLite compatible)
    sql_statements = [
        # Zipcodes table - essential for the scheduler
        """
        CREATE TABLE IF NOT EXISTS zipcodes (
            zipcode_id INTEGER PRIMARY KEY AUTOINCREMENT,
            zipcode TEXT UNIQUE NOT NULL,
            last_for_sale_fetch DATETIME,
            last_sold_fetch DATETIME,
            for_sale_fetch_frequency_days INTEGER DEFAULT 1,
            sold_fetch_frequency_days INTEGER DEFAULT 7,
            for_sale_request_url TEXT,
            sold_request_url TEXT
        )
        """,
        
        # Pipeline tables - essential for job management
        """
        CREATE TABLE IF NOT EXISTS pipline_tables (
            job_id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_type TEXT NOT NULL,
            payload TEXT,
            status TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            started_at DATETIME,
            completed_at DATETIME,
            error_message TEXT
        )
        """,
        
        # Property table - essential for storing property data
        """
        CREATE TABLE IF NOT EXISTS property (
            property_id INTEGER PRIMARY KEY AUTOINCREMENT,
            redfin_property_id TEXT UNIQUE,
            zillow_property_id TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            zipcode TEXT,
            price REAL,
            bedrooms INTEGER,
            bathrooms REAL,
            square_feet INTEGER,
            lot_size REAL,
            year_built INTEGER,
            property_type TEXT,
            status TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """,
        
        # Listing table - for storing listing information
        """
        CREATE TABLE IF NOT EXISTS listing (
            listing_id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER,
            redfin_listing_id TEXT UNIQUE,
            listing_price REAL,
            listing_date DATE,
            status TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (property_id) REFERENCES property (property_id)
        )
        """,
        
        # Price history table - for tracking price changes
        """
        CREATE TABLE IF NOT EXISTS price_history (
            price_history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER,
            listing_id INTEGER,
            price REAL,
            date DATE,
            event_type TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (property_id) REFERENCES property (property_id),
            FOREIGN KEY (listing_id) REFERENCES listing (listing_id)
        )
        """,
        
        # School table - for school information
        """
        CREATE TABLE IF NOT EXISTS school (
            school_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            rating REAL,
            type TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """,
        
        # Property school join table - for property-school relationships
        """
        CREATE TABLE IF NOT EXISTS property_school_join (
            property_id INTEGER,
            school_id INTEGER,
            PRIMARY KEY (property_id, school_id),
            FOREIGN KEY (property_id) REFERENCES property (property_id),
            FOREIGN KEY (school_id) REFERENCES school (school_id)
        )
        """,
        
        # Transaction table - for property transactions
        """
        CREATE TABLE IF NOT EXISTS transaction (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER,
            sale_price REAL,
            sale_date DATE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (property_id) REFERENCES property (property_id)
        )
        """,
        
        # Property change table - for tracking property changes
        """
        CREATE TABLE IF NOT EXISTS property_change (
            change_id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER,
            field_name TEXT,
            old_value TEXT,
            new_value TEXT,
            change_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (property_id) REFERENCES property (property_id)
        )
        """,
        
        # Status history table - for tracking status changes
        """
        CREATE TABLE IF NOT EXISTS status_history (
            status_history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER,
            listing_id INTEGER,
            status TEXT,
            date DATE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (property_id) REFERENCES property (property_id),
            FOREIGN KEY (listing_id) REFERENCES listing (listing_id)
        )
        """,
        
        # Zestimate history table - for tracking Zillow estimates
        """
        CREATE TABLE IF NOT EXISTS zestimate_history (
            zestimate_id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER,
            zestimate_value REAL,
            date DATE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (property_id) REFERENCES property (property_id)
        )
        """
    ]
    
    print("Setting up database tables...")
    
    # Execute each SQL statement
    with engine.connect() as conn:
        for i, sql in enumerate(sql_statements, 1):
            try:
                conn.execute(text(sql))
                conn.commit()
                print(f"✅ Created table {i}/{len(sql_statements)}")
            except Exception as e:
                print(f"Warning creating table {i}: {e}")
    
    print("✅ Database setup complete!")


def add_sample_zipcode():
    """Add a sample zipcode for testing."""
    session = SessionLocal()
    try:
        from sqlalchemy import text
        
        # Check if zipcode already exists using raw SQL
        result = session.execute(
            text("SELECT * FROM zipcodes WHERE zipcode = :zipcode"),
            {"zipcode": "85297"}
        ).fetchone()
        
        if not result:
            # Insert new zipcode using raw SQL
            session.execute(
                text("""
                    INSERT INTO zipcodes (zipcode, for_sale_fetch_frequency_days, sold_fetch_frequency_days)
                    VALUES (:zipcode, :for_sale_days, :sold_days)
                """),
                {
                    "zipcode": "85297",
                    "for_sale_days": 1,
                    "sold_days": 7
                }
            )
            session.commit()
            print("✅ Added sample zipcode 85297")
        else:
            print("✅ Sample zipcode 85297 already exists")
            
    except Exception as e:
        print(f"Could not add sample zipcode: {e}")
    finally:
        session.close()


def main():
    """Main setup function."""
    print("Real Estate Data Pipeline - Database Setup")
    print("=" * 50)
    
    try:
        create_essential_tables()
        print("")
        add_sample_zipcode()
        print("")
        print("Database setup completed successfully!")
        print("The system is now ready to run!")
        
    except Exception as e:
        print(f"Database setup failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

