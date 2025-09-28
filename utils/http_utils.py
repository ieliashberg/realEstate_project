"""
HTTP Utilities

Pure HTTP request utilities without user agent management logic.
User agents are provided by the caller or UserAgentService.
"""

from curl_cffi import requests
import json
import logging
import time
from typing import Dict, Optional, Any

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
    Make an HTTP request with curl_cffi
    
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
            timeout=timeout,
            impersonate="chrome110"
        )
        
        response.raise_for_status()
        return response.text
    
    except Exception as e:
        return None


def fetch_html_via_https(url: str, base_heads: Dict[str, str] = None, proxy: Dict[str, str] = None) -> Optional[str]:
    """
    Legacy function for backward compatibility with user agent rotation.
    Use make_request() for new code.
    """
    headers = base_heads or REDFIN_HEADERS
    
    # Get user agents from database and try each one
    try:
        from dataBase import SessionLocal
        from services.user_agent_service import UserAgentService
        
        session = SessionLocal()
        ua_service = UserAgentService(session)
        user_agents = ua_service.get_working_user_agents(15)
        session.close()
        
        if not user_agents:
            user_agents = ["Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"]
    except Exception:
        user_agents = ["Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"]
    
    # Try each user agent until one works
    for ua in user_agents:
        headers_with_ua = {**headers, "User-Agent": ua}
        result = make_request(url, headers=headers_with_ua, proxies=proxy)
        if result is not None:
            return result
    
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


# Legacy aliases for backward compatibility
redfin_base_headers = REDFIN_HEADERS
zillow_base_headers = ZILLOW_HEADERS
