"""
Pytest configuration and shared fixtures for the real estate project tests.
"""

import pytest
import os
import sys
from unittest.mock import Mock, patch
from datetime import datetime, timezone

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.database.connection import SessionLocal


@pytest.fixture
def mock_session():
    """Provide a mock database session for testing."""
    session = Mock()
    session.query.return_value.filter_by.return_value.first.return_value = None
    session.query.return_value.filter_by.return_value.one.side_effect = Exception("Not found")
    session.add = Mock()
    session.commit = Mock()
    session.rollback = Mock()
    session.close = Mock()
    session.flush = Mock()
    return session


@pytest.fixture
def sample_property_payload():
    """Sample property payload for testing."""
    return {
        "property_id": 12345,
        "address": "123 Main St",
        "city": "Gilbert",
        "state": "AZ",
        "zipcode": "85297",
        "redfin_property_id": "12345678",
        "listing_id": 98765,
        "isNewProperty": True,
        "url": "/AZ/Gilbert/123-Main-St-85297/home/12345678"
    }


@pytest.fixture
def sample_redfin_html():
    """Sample Redfin HTML with property data."""
    return '''
    <!DOCTYPE html>
    <html>
    <head><title>Test Property</title></head>
    <body>
    <script type="text/javascript">
    root.__reactServerState.InitialContext = {
        "ReactServerAgent.cache": {
            "dataCache": {
                "/stingray/api/home/details/aboveTheFold": {
                    "res": {
                        "text": "{}&&{\\"version\\":608,\\"errorMessage\\":\\"Success\\",\\"resultCode\\":0,\\"payload\\":{\\"addressSectionInfo\\":{\\"street\\":\\"123 Main St\\",\\"city\\":\\"Gilbert\\",\\"state\\":\\"AZ\\",\\"zip\\":\\"85297\\"},\\"mediaBrowserInfo\\":{\\"photos\\":[]}}}"
                    }
                },
                "/stingray/api/home/details/belowTheFold": {
                    "res": {
                        "text": "{}&&{\\"version\\":608,\\"errorMessage\\":\\"Success\\",\\"resultCode\\":0,\\"payload\\":{\\"amenitiesInfo\\":{\\"provider\\":\\"ARMLS\\",\\"superGroups\\":[{\\"types\\":[28],\\"amenityGroups\\":[{\\"groupTitle\\":\\"Tax Information\\",\\"amenityEntries\\":[{\\"amenityName\\":\\"Tax Annual Amount\\",\\"amenityValues\\":[\\"$1,866\\"]}]}]},\\"schoolsAndDistrictsInfo\\":{\\"servingThisHomeSchools\\":[{\\"name\\":\\"Test Elementary\\",\\"rating\\":5,\\"is_elementary\\":true}]},\\"propertyHistoryInfo\\":{\\"events\\":[{\\"price\\":635000,\\"eventDescription\\":\\"Sold\\",\\"eventDate\\":1751007600000}]}}}}"
                    }
                }
            }
        }
    };
    </script>
    </body>
    </html>
    '''


@pytest.fixture
def sample_zillow_html():
    """Sample Zillow HTML with zestimate data."""
    return '''
    <!DOCTYPE html>
    <html>
    <head><title>Zillow Test</title></head>
    <body>
    <script type="text/javascript">
    window.__INITIAL_STATE__ = {
        "address": {
            "rentZestimate": 2500,
            "rentZestimateRangeHigh": 2700,
            "rentZestimateRangeLow": 2300
        }
    };
    </script>
    </body>
    </html>
    '''


@pytest.fixture
def sample_job_payload():
    """Sample job payload for testing."""
    return {
        "property_id": 12345,
        "address": "123 Main St",
        "city": "Gilbert",
        "state": "AZ",
        "zipcode": "85297",
        "test": True
    }


@pytest.fixture(autouse=True)
def setup_logging():
    """Set up logging for tests."""
    import logging
    logging.basicConfig(level=logging.DEBUG)
    return logging.getLogger(__name__)


@pytest.fixture
def mock_http_response():
    """Mock HTTP response for testing."""
    response = Mock()
    response.status_code = 200
    response.text = "<html><body>Test HTML</body></html>"
    response.raise_for_status = Mock()
    return response


@pytest.fixture
def mock_playwright():
    """Mock Playwright for testing."""
    with patch('zestimate_helper.sync_playwright') as mock_pw:
        mock_browser = Mock()
        mock_context = Mock()
        mock_page = Mock()
        
        mock_pw.return_value.__enter__.return_value = mock_pw.return_value
        mock_pw.return_value.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        mock_page.goto.return_value = None
        mock_page.content.return_value = "<html><body>Test HTML</body></html>"
        mock_page.close.return_value = None
        mock_context.close.return_value = None
        mock_browser.close.return_value = None
        
        yield mock_pw
