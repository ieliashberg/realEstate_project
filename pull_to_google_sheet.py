from dataBase import (
    SessionLocal,
    Property,
    Listing,
    Price_History,
    Property_School_Join,
    School,
)

import math, json
from decimal import Decimal
from datetime import date, datetime
import numpy as np
import pandas as pd
from pandas import json_normalize

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# If you only need to write (and read) spreadsheets:
SCOPES = ['https://www.googleapis.com/auth/spreadsheets',
          'https://www.googleapis.com/auth/drive.metadata.readonly',
          ]

# ─── embed your OAuth “client secret” JSON here ───
# You get these values by creating a desktop‐app client in
# GCP Console → APIs & Services → Credentials → OAuth 2.0 Client IDs
CLIENT_CONFIG = {
    "installed": {"client_id": "463501623183-nkjaf5erg5jt5jkicuc1oeiltkdobuj2.apps.googleusercontent.com",
                  "project_id": "real-estate-project-463201",
                  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                  "token_uri": "https://oauth2.googleapis.com/token",
                  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                  "client_secret": "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",
                  "redirect_uris": ["http://localhost"]
                  }
}


def pull_information_for_sheets() -> pd.DataFrame:
    session = SessionLocal()
    try:
        properties = (
            session.query(Property)
            .filter(Property.is_on_market == True)
            .all()
        )

        results = []
        for prop in properties:
            listing = (
                session.query(Listing)
                .filter(Listing.property_id == prop.property_id)
                .order_by(Listing.list_date.desc())
                .first()
            )

            oldest_ph = None
            newest_ph = None
            if listing:
                oldest_ph = (
                    session.query(Price_History)
                    .filter(Price_History.listing_id == listing.listing_id)
                    .order_by(Price_History.change_date.asc())
                    .first()
                )
                newest_ph = (
                    session.query(Price_History)
                    .filter(Price_History.listing_id == listing.listing_id)
                    .order_by(Price_History.change_date.desc())
                    .first()
                )

            schools = (
                session.query(School)
                .join(
                    Property_School_Join,
                    School.school_id == Property_School_Join.school_id,
                )
                .filter(Property_School_Join.property_id == prop.property_id)
                .all()
            )
            school_data = [
                {
                    "name": school.name,
                    "rating": school.rating,
                }
                for school in schools
            ]

            result = {
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
                "listing": None,
                "oldest_price_history": None,
                "newest_price_history": None,
                "schools": school_data,
            }

            if listing:
                result["listing"] = {
                    "list_date": listing.list_date,
                    "url": listing.url,
                }

            if oldest_ph:
                result["oldest_price_history"] = {
                    "old_price": oldest_ph.old_price,
                }

            if newest_ph:
                result["newest_price_history"] = {
                    "old_price": newest_ph.old_price,
                    "new_price": newest_ph.new_price,
                    "change_date": newest_ph.change_date,
                }
            results.append(result)

        data_frame = json_normalize(results, sep='.')
        return data_frame
    finally:
        session.close()


def get_sheets_service():
    # run_local_server() will open the browser and ask the user to pick
    # their Google account and grant the SHEETS scope
    flow = InstalledAppFlow.from_client_config(CLIENT_CONFIG, SCOPES)
    creds = flow.run_local_server(port=0)
    return build("sheets", "v4", credentials=creds)


def _sanitize(o):
    # 1) Decimal → float
    if isinstance(o, Decimal):
        return float(o)

    # 2) datetime/date/timestamp → ISO str
    if isinstance(o, (datetime, date, pd.Timestamp)):
        return o.isoformat()

    # 3) floats: catch NaN/±Inf
    if isinstance(o, float):
        if math.isnan(o) or math.isinf(o):
            return None
        return o

    # 4) numpy scalars → Python scalar
    if isinstance(o, np.generic):
        return o.item()

    # 5) lists or dicts → JSON‐encode the whole thing as a string
    if isinstance(o, (list, dict)):
        return json.dumps(o, default=lambda x: None)

    # 6) leave everything else (int, str, bool, None) alone
    return o

def append_rows(sheet_id: str, range_name: str, df: pd.DataFrame, include_header: bool = True):
    svc = get_sheets_service()

    # 1) pull raw rows
    rows = []
    if include_header:
        rows.append(df.columns.tolist())
    rows.extend(df.values.tolist())

    # 2) sanitize every cell
    clean_rows = [
        [_sanitize(cell) for cell in row]
        for row in rows
    ]

    # 3) send to Sheets
    svc.spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range=range_name,
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": clean_rows}
    ).execute()


def get_creds():
    flow = InstalledAppFlow.from_client_config(
        CLIENT_CONFIG,
        SCOPES,
    )
    return flow.run_local_server(port=0)


def choose_spreadsheet(creds):
    drive = build('drive', 'v3', credentials=creds)
    resp = drive.files().list(
        q="mimeType='application/vnd.google-apps.spreadsheet'",
        pageSize=50,
        fields="files(id, name)"
    ).execute()
    sheets = resp.get('files', [])

    print("\nPlease select a spreadsheet:\n")
    for i, f in enumerate(sheets, start=1):
        print(f"  {i}. {f['name']}  (id={f['id']})")
    print("  N. Create a brand-new spreadsheet\n")

    choice = input("Enter number or N: ").strip().lower()
    if choice == 'n':
        title = input("New sheet title: ").strip()
        sheets_api = build('sheets', 'v4', credentials=creds)
        created = sheets_api.spreadsheets().create(
            body={'properties': {'title': title}}
        ).execute()
        new_id = created['spreadsheetId']
        print(f"→ Created “{title}” (id={new_id})\n")
        return new_id

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(sheets):
            return sheets[idx]['id']
    except ValueError:
        pass

    print("Invalid choice, try again.")
    return choose_spreadsheet(creds)


if __name__ == "__main__":
    # when you run this, you'll get a browser popup to grant
    # access to YOUR_CLIENT_ID, and a token is cached in memory.
    df = pull_information_for_sheets()
    print(df.head())

    creds = get_creds()  # OAuth2 stuff
    spreadsheet_id = choose_spreadsheet(creds)  # prompt & return a valid id
    append_rows(spreadsheet_id, "Sheet1!A1", df)

    print("Done!")



# if __name__ == "__main__":
