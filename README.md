# Real Estate Data Pipeline

A comprehensive Python-based data pipeline for scraping, processing, and managing real estate data pulled from Redfin and Zillow.

## Features

- **Multi-source data scraping** from Redfin and Zillow
- **Automated property data collection** including prices, details, and market status
- **Database management** with SQLAlchemy and PostgreSQL/SQLite support
- **Google Sheets integration** for data export and analysis
- **User agent rotation** to avoid detection and rate limiting
- **Comprehensive testing suite** with unit and integration tests

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL (optional, SQLite supported by default)

### Installation
 **Set up the database**
   ```bash
   python setup_database.py
   ```

### Basic Usage

1. **Run the main pipeline**
   ```bash
   python scripts/main.py
   ```

2. **Export data to Google Sheets**
   ```bash
   python pull_to_google_sheet.py
   ```

3. **Create new zipcode entries**
   ```bash
   python create_new_zip.py
   ```

## Project Structure

```
realEstate_project/
├── src/                    # Core application code
│   ├── config/            # Configuration settings
│   ├── database/          # Database models and connection
│   ├── pipeline/          # Job queue and processing
│   ├── scrapers/          # Web scraping modules
│   └── utils/             # Utility functions
├── tests/                 # Test suite
├── scripts/               # Executable scripts
├── dumps/                 # Data export files
└── requirements.txt       # Python dependencies
```

### Google Sheets Integration
- Requires Google OAuth credentials
- Set up in Google Cloud Console
- Configure environment variables for authentication

## Testing

Run the test suite:

```bash
# Run all tests
python -m pytest tests/

# Run specific test categories
python tests/run_tests.py
```

## Data Sources

- **Redfin**: Property listings, price history, school data, etc.
- **Zillow**: Rental estimates