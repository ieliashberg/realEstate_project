#!/usr/bin/env python3
"""
Simple script to fetch HTML from any URL.
Reuses existing HTTP handling utilities from the project.
"""

import sys
import os
import time
import logging
from typing import List, Dict, Optional
from pathlib import Path
from urllib.parse import urlparse

# Add the project directory to the path so we can import the modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.http_utils import fetch_html_via_https, REDFIN_HEADERS as redfin_base_headers

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_redfin_html(url: str, delay: float = 1.0) -> Optional[str]:
    """
    Fetch HTML from any Redfin URL.
    
    Args:
        url: The Redfin URL to fetch (e.g., "https://www.redfin.com/zipcode/94087")
        delay: Delay in seconds before making the request (to be respectful)
    
    Returns:
        HTML content as string, or None if failed
    """
    try:
        logger.info(f"Fetching HTML from: {url}")
        
        # Add delay to be respectful to Redfin's servers
        if delay > 0:
            time.sleep(delay)
        
        # Use existing HTTP handling code
        html = fetch_html_via_https(url, redfin_base_headers)
        
        logger.info(f"Successfully fetched {len(html)} characters from {url}")
        return html
        
    except Exception as e:
        logger.error(f"Failed to fetch HTML from {url}: {e}")
        return None


def fetch_multiple_urls(urls: List[str], delay: float = 2.0, 
                       output_dir: str = "redfin_html") -> Dict[str, Optional[str]]:
    """
    Fetch HTML from multiple Redfin URLs.
    
    Args:
        urls: List of Redfin URLs to fetch
        delay: Delay in seconds between requests
        output_dir: Directory to save HTML files (optional)
    
    Returns:
        Dictionary mapping URL to HTML content (None if failed)
    """
    results = {}
    
    # Create output directory if specified
    if output_dir:
        Path(output_dir).mkdir(exist_ok=True)
        logger.info(f"HTML files will be saved to: {output_dir}")
    
    for i, url in enumerate(urls):
        logger.info(f"Processing URL {i+1}/{len(urls)}: {url}")
        
        html = fetch_redfin_html(url, delay=0)  # No delay here since we handle it below
        
        results[url] = html
        
        # Save to file if HTML was fetched successfully
        if html and output_dir:
            # Create a safe filename from the URL
            filename = create_safe_filename(url)
            filepath = f"{output_dir}/{filename}"
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(html)
                logger.info(f"Saved HTML to: {filepath}")
            except Exception as e:
                logger.error(f"Failed to save HTML for {url}: {e}")
        
        # Add delay between requests (except for the last one)
        if i < len(urls) - 1 and delay > 0:
            logger.info(f"Waiting {delay} seconds before next request...")
            time.sleep(delay)
    
    return results


def create_safe_filename(url: str) -> str:
    """
    Create a safe filename from a URL.
    
    Args:
        url: The URL to convert to a filename
    
    Returns:
        Safe filename string
    """
    # Parse the URL
    parsed = urlparse(url)
    
    # Extract path and clean it up
    path = parsed.path.strip('/')
    if not path:
        path = "home"
    
    # Replace problematic characters
    safe_path = path.replace('/', '_').replace('?', '_').replace('&', '_')
    
    # Add .html extension
    if not safe_path.endswith('.html'):
        safe_path += '.html'
    
    return f"redfin_{safe_path}"


def main():
    """Main function to run the script."""
                                                     # PICK WHICH URLS TO FETCH HERE!!!!
    urls = [
        "https://www.redfin.com/AZ/Gilbert/3742-E-Sandy-Way-85297/home/27485241",
        "https://www.redfin.com/AZ/Gilbert/4667-E-Reins-Rd-85297/home/27517976",
        "https://www.redfin.com/AZ/Phoenix/1911-E-Lawrence-Rd-85016/home/28253273",
        "https://www.redfin.com/AZ/Gilbert/4906-S-Verbena-Ave-85298/home/27854612",
        "https://www.redfin.com/AZ/Gilbert/2128-E-Clipper-Ln-85234/home/26862445",
        "https://www.redfin.com/AZ/Gilbert/232-W-San-Angelo-St-85233/home/26902458",
        "https://www.redfin.com/AZ/Gilbert/3175-E-Merrill-Ave-85234/home/27010915",
    ]
    
    print("Redfin HTML Fetcher")
    print("=" * 40)
    print(f"Will fetch HTML for {len(urls)} URLs")
    print("URLs:")
    for url in urls:
        print(f"  - {url}")
    print()
    
    # Fetch HTML for all URLs
    results = fetch_multiple_urls(
        urls=urls,
        delay=1.0,  # 2 second delay between requests
        output_dir="tests/redfin_individual_homes_htmls"                 # PICK WHICH DIRECTORY TO SAVE TO HERE!!!!
    )
    
    # Print summary
    print("\n" + "=" * 40)
    print("SUMMARY")
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
    
    print(f"\nHTML files saved to: tests/redfin_individual_homes_htmls")


if __name__ == "__main__":
    main() 