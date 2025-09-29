#!/usr/bin/env python3
"""
Script to fetch sample HTML data for testing and analysis.

This script fetches HTML from various real estate websites and saves them
for testing purposes.
"""

import sys
import os
from pathlib import Path

# Add the project directory to the path so we can import the modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.http import fetch_multiple_urls
from src.config.settings import REDFIN_HEADERS, ZILLOW_HEADERS
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_redfin_samples():
    """Fetch sample Redfin HTML files."""
    urls = [
        "https://www.redfin.com/AZ/Gilbert/3742-E-Sandy-Way-85297/home/27485241",
        "https://www.redfin.com/AZ/Gilbert/4667-E-Reins-Rd-85297/home/27517976",
        "https://www.redfin.com/AZ/Phoenix/1911-E-Lawrence-Rd-85016/home/28253273",
        "https://www.redfin.com/AZ/Gilbert/4906-S-Verbena-Ave-85298/home/27854612",
        "https://www.redfin.com/AZ/Gilbert/2128-E-Clipper-Ln-85234/home/26862445",
        "https://www.redfin.com/AZ/Gilbert/232-W-San-Angelo-St-85233/home/26902458",
        "https://www.redfin.com/AZ/Gilbert/3175-E-Merrill-Ave-85234/home/27010915",
    ]
    
    print("Fetching Redfin Sample HTML Files")
    print("=" * 40)
    print(f"Will fetch HTML for {len(urls)} URLs")
    print("URLs:")
    for url in urls:
        print(f"  - {url}")
    print()
    
    # Fetch HTML for all URLs
    results = fetch_multiple_urls(
        urls=urls,
        delay=1.0,  # 1 second delay between requests
        output_dir="tests/redfin_individual_homes_htmls",
        headers=REDFIN_HEADERS
    )
    
    # Print summary
    print_summary(results, "Redfin")


def fetch_zillow_samples():
    """Fetch sample Zillow HTML files."""
    urls = [
        "https://www.zillow.com/rental-manager/price-my-rental/results/1169-sesame-dr-sunnyvale-ca-94087/",
        "https://www.zillow.com/rental-manager/price-my-rental/results/123-main-st-gilbert-az-85297/",
    ]
    
    print("Fetching Zillow Sample HTML Files")
    print("=" * 40)
    print(f"Will fetch HTML for {len(urls)} URLs")
    print("URLs:")
    for url in urls:
        print(f"  - {url}")
    print()
    
    # Fetch HTML for all URLs
    results = fetch_multiple_urls(
        urls=urls,
        delay=2.0,  # 2 second delay between requests
        output_dir="tests/zillow_samples",
        headers=ZILLOW_HEADERS
    )
    
    # Print summary
    print_summary(results, "Zillow")


def print_summary(results: dict, service_name: str):
    """Print summary of fetch results."""
    print("\n" + "=" * 40)
    print(f"{service_name} FETCH SUMMARY")
    print("=" * 40)
    
    successful = sum(1 for html in results.values() if html is not None)
    failed = len(results) - successful
    
    print(f"Total URLs processed: {len(results)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    
    if failed > 0:
        print("\nFailed URLs:")
        for url, html in results.items():
            if html is None:
                print(f"  - {url}")


def main():
    """Main function to run the script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Fetch sample HTML data for testing")
    parser.add_argument("--service", choices=["redfin", "zillow", "all"], 
                       default="redfin", help="Which service to fetch samples from")
    
    args = parser.parse_args()
    
    if args.service in ["redfin", "all"]:
        fetch_redfin_samples()
    
    if args.service in ["zillow", "all"]:
        fetch_zillow_samples()
    
    print("\nSample fetching completed!")


if __name__ == "__main__":
    main()
