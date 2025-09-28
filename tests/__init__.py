"""
Real Estate Project Test Suite

This package contains comprehensive tests for the real estate data scraping and processing pipeline.
"""

import sys
import os

# Add the project root to the Python path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
