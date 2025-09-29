"""
Google Sheets integration for real estate data export.

This module provides functionality to export real estate property data
from the database to Google Sheets.
"""

import json
import os
import math
from decimal import Decimal
from datetime import date, datetime
from typing import List, Dict, Any, Optional, Union

import pandas as pd
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from src.database.connection import (
    SessionLocal,
    Property,
    Listing,
    Price_History,
    Property_School_Join,
    School,
)

# Google API scopes
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.metadata.readonly',
]

# OAuth configuration - should be moved to environment variables
CLIENT_CONFIG = {
    "installed": {
        "client_id": os.getenv("GOOGLE_CLIENT_ID", "463501623183-nkjaf5erg5jt5jkicuc1oeiltkdobuj2.apps.googleusercontent.com"),
        "project_id": os.getenv("GOOGLE_PROJECT_ID", "real-estate-project-463201"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", "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"),
        "redirect_uris": ["http://localhost"]
    }
}


def get_property_data() -> pd.DataFrame:
    """Fetch property data from database and return as DataFrame."""
    with SessionLocal() as session:
        properties = session.query(Property).filter(Property.is_on_market == True).all()
        
        results = [_build_property_record(session, prop) for prop in properties]
        
        return pd.json_normalize(results, sep='.')


def _build_property_record(session, prop: Property) -> Dict[str, Any]:
    """Build a property record with related data."""
    listing = _get_latest_listing(session, prop.property_id)
    price_history = _get_price_history(session, listing) if listing else (None, None)
    schools = _get_school_data(session, prop.property_id)
    
    record = {
        "property_id": prop.property_id,
        "address": prop.address,
        "city": prop.city,
        "state": prop.state,
        "zip": prop.zipcode,
        "beds": prop.beds,
        "baths": prop.baths,
        "current_zestimate": prop.current_zestimate,
        "covered_spaces": prop.covered_spaces,
        "year_built": prop.year_built,
        "stories": prop.stories,
        "hoa": prop.hoa,
        "tax_annual_amount": prop.tax_annual_amount,
        "schools": schools,
    }
    
    # Add listing data if available
    if listing:
        record["listing"] = {
            "list_date": listing.list_date,
            "url": listing.url,
        }
    
    # Add price history data if available
    oldest_ph, newest_ph = price_history
    if oldest_ph:
        record["oldest_price_history"] = {"old_price": oldest_ph.old_price}
    if newest_ph:
        record["newest_price_history"] = {
            "old_price": newest_ph.old_price,
            "new_price": newest_ph.new_price,
            "change_date": newest_ph.change_date,
        }
    
    return record


def _get_latest_listing(session, property_id: int) -> Optional[Listing]:
    """Get the latest listing for a property."""
    return (
        session.query(Listing)
        .filter(Listing.property_id == property_id)
        .order_by(Listing.list_date.desc())
        .first()
    )


def _get_price_history(session, listing: Listing) -> tuple[Optional[Price_History], Optional[Price_History]]:
    """Get oldest and newest price history for a listing."""
    oldest = (
        session.query(Price_History)
        .filter(Price_History.listing_id == listing.listing_id)
        .order_by(Price_History.change_date.asc())
        .first()
    )
    newest = (
        session.query(Price_History)
        .filter(Price_History.listing_id == listing.listing_id)
        .order_by(Price_History.change_date.desc())
        .first()
    )
    return oldest, newest


def _get_school_data(session, property_id: int) -> List[Dict[str, Any]]:
    """Get school data for a property."""
    schools = (
        session.query(School)
        .join(Property_School_Join, School.school_id == Property_School_Join.school_id)
        .filter(Property_School_Join.property_id == property_id)
        .all()
    )
    return [{"name": school.name, "rating": school.rating} for school in schools]


def _get_google_credentials():
    """Get Google API credentials via OAuth flow."""
    flow = InstalledAppFlow.from_client_config(CLIENT_CONFIG, SCOPES)
    return flow.run_local_server(port=0)


def _sanitize_cell_value(value: Any) -> Any:
    """Sanitize cell values for Google Sheets compatibility."""
    if isinstance(value, Decimal):
        return float(value)
    
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    
    if isinstance(value, (list, dict)):
        return json.dumps(value, default=lambda x: None)
    
    return value

def append_data_to_sheet(sheet_id: str, range_name: str, df: pd.DataFrame, include_header: bool = True) -> None:
    """Append DataFrame data to Google Sheet."""
    creds = _get_google_credentials()
    service = build("sheets", "v4", credentials=creds)
    
    # Prepare rows with optional header
    rows = [df.columns.tolist()] if include_header else []
    rows.extend(df.values.tolist())
    
    # Sanitize all cell values
    sanitized_rows = [
        [_sanitize_cell_value(cell) for cell in row]
        for row in rows
    ]
    
    # Send to Google Sheets
    service.spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range=range_name,
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": sanitized_rows}
    ).execute()


def select_spreadsheet() -> str:
    """Allow user to select existing spreadsheet or create new one."""
    creds = _get_google_credentials()
    drive = build('drive', 'v3', credentials=creds)
    
    # Get existing spreadsheets
    response = drive.files().list(
        q="mimeType='application/vnd.google-apps.spreadsheet'",
        pageSize=50,
        fields="files(id, name)"
    ).execute()
    spreadsheets = response.get('files', [])
    
    print("\nAvailable spreadsheets:")
    for i, sheet in enumerate(spreadsheets, 1):
        print(f"  {i}. {sheet['name']} (id={sheet['id']})")
    print("  N. Create new spreadsheet")
    
    while True:
        choice = input("\nSelect option: ").strip().lower()
        
        if choice == 'n':
            return _create_new_spreadsheet(creds)
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(spreadsheets):
                return spreadsheets[idx]['id']
        except ValueError:
            pass
        
        print("Invalid choice. Please try again.")


def _create_new_spreadsheet(creds) -> str:
    """Create a new Google Spreadsheet."""
    title = input("Enter spreadsheet title: ").strip()
    service = build('sheets', 'v4', credentials=creds)
    
    created = service.spreadsheets().create(
        body={'properties': {'title': title}}
    ).execute()
    
    sheet_id = created['spreadsheetId']
    print(f"Created '{title}' (id={sheet_id})")
    return sheet_id


def main() -> None:
    """Main function to export property data to Google Sheets."""
    print("Fetching property data from database...")
    df = get_property_data()
    print(f"Found {len(df)} properties")
    print("\nSample data:")
    print(df.head())
    
    print("\nSelect spreadsheet for export...")
    spreadsheet_id = select_spreadsheet()
    
    print("Uploading data to Google Sheets...")
    append_data_to_sheet(spreadsheet_id, "Sheet1!A1", df)
    
    print("Export completed successfully!")


if __name__ == "__main__":
    main()
