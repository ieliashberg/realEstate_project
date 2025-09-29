"""
HTTP Utilities

Pure HTTP request utilities without user agent management logic.
User agents are provided by the caller or UserAgentService.
"""

import json
import logging
import time
from typing import Dict, Optional, Any, List
from pathlib import Path
from urllib.parse import urlparse
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Base headers for different sites
REDFIN_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Ch-Ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

ZILLOW_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Priority": "u=0, i",
    "Sec-Ch-Ua": '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


def make_request(url: str, headers: Dict[str, str] = None, proxies: Dict[str, str] = None, timeout: int = 20) -> Optional[str]:
    """
    Make an HTTP request using regular requests library
    
    Args:
        url: URL to request
        headers: HTTP headers (should include User-Agent)
        proxies: Proxy configuration
        timeout: Request timeout in seconds
    
    Returns:
        Response text or None if failed
    """
    if headers is None:
        headers = {}
    
    try:
        response = requests.get(
            url,
            headers=headers,
            proxies=proxies,
            timeout=timeout
        )
        
        response.raise_for_status()
        return response.text
        
    except Exception as e:
        logger.error(f"HTTP request failed for {url}: {type(e).__name__}: {e}")
        return None


def fetch_html_via_https(url: str, base_heads: Dict[str, str] = None, proxy: Dict[str, str] = None) -> Optional[str]:
    """
    Legacy function for backward compatibility with user agent rotation.
    Use make_request() for new code.
    """
    headers = base_heads or REDFIN_HEADERS
    
    # Get user agents from database and try each one
    try:
        from src.database.connection import SessionLocal
        from src.scrapers.user_agents.service import UserAgentService
        
        session = SessionLocal()
        ua_service = UserAgentService(session)
        user_agents = ua_service.get_working_user_agents(15)
        session.close()
        
        if not user_agents:
            user_agents = ["Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"]
    except Exception as e:
        logger.warning(f"Failed to get user agents from database: {e}")
        user_agents = ["Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"]
    
    # Try each user agent until one works
    for i, ua in enumerate(user_agents):
        logger.info(f"Trying user agent {i+1}/{len(user_agents)}: {ua[:50]}...")
        headers_with_ua = {**headers, "User-Agent": ua}
        result = make_request(url, headers=headers_with_ua, proxies=proxy)
        if result is not None:
            logger.info(f"Success with user agent {i+1}")
            return result
        else:
            logger.warning(f"Failed with user agent {i+1}")
            # Add delay between attempts to avoid rate limiting
            if i < len(user_agents) - 1:  # Don't delay after the last attempt
                delay = 2 + (i)  # Increasing delay: 8s, 10s, 12s, etc.
                logger.info(f"Waiting {delay:.1f} seconds before next attempt...")
                time.sleep(delay)
    
    logger.error(f"All {len(user_agents)} user agents failed for {url}")
    return None


def strip_json_beginning(text: str, prefix: str) -> str:
    """
    Strip everything before and including the given prefix from text.
    If the prefix is not found, raise ValueError.
    """
    if prefix not in text:
        raise ValueError(f"Prefix '{prefix}' not found in text")
    
    start_index = text.find(prefix) + len(prefix)
    remaining_text = text[start_index:]
    
    # Try to find valid JSON after the prefix
    # Look for the first complete JSON object/array
    brace_count = 0
    bracket_count = 0
    in_string = False
    escape_next = False
    
    for i, char in enumerate(remaining_text):
        if escape_next:
            escape_next = False
            continue
            
        if char == '\\':
            escape_next = True
            continue
            
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
            
        if not in_string:
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
            elif char == '[':
                bracket_count += 1
            elif char == ']':
                bracket_count -= 1
                
            # If we've closed all braces and brackets, we have complete JSON
            if brace_count == 0 and bracket_count == 0 and i > 0:
                try:
                    # Try to parse the JSON to validate it
                    json.loads(remaining_text[:i+1])
                    return remaining_text[:i+1]
                except json.JSONDecodeError:
                    continue
    
    # If we get here, the JSON might be malformed
    raise ValueError("Could not find complete valid JSON after prefix")


def create_safe_filename(url: str, prefix: str = "") -> str:
    """
    Create a safe filename from a URL.
    
    Args:
        url: The URL to convert to a filename
        prefix: Optional prefix for the filename
    
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
    
    # Add prefix if provided
    if prefix:
        safe_path = f"{prefix}_{safe_path}"
    
    return safe_path


def fetch_multiple_urls(urls: List[str], delay: float = 2.0, 
                       output_dir: Optional[str] = None, 
                       headers: Optional[Dict[str, str]] = None) -> Dict[str, Optional[str]]:
    """
    Fetch HTML from multiple URLs with rate limiting.
    
    Args:
        urls: List of URLs to fetch
        delay: Delay in seconds between requests
        output_dir: Directory to save HTML files (optional)
        headers: HTTP headers to use for requests
    
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
        
        html = fetch_html_via_https(url, headers)
        results[url] = html
        
        # Save to file if HTML was fetched successfully
        if html and output_dir:
            filename = create_safe_filename(url)
            filepath = Path(output_dir) / filename
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


# Legacy aliases for backward compatibility
redfin_base_headers = REDFIN_HEADERS
zillow_base_headers = ZILLOW_HEADERS
