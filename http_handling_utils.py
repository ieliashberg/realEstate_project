from user_agents import get_ua
from curl_cffi import requests

import json
import logging

# configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

base_headers = {
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


def fetch_html_via_https(url: str, proxy: dict[str, str] | None = None):
    header_with_ua = put_ua_in_header()
    resp = requests.get(
        url=url,
        headers=header_with_ua,
        proxies=proxy,
        impersonate="chrome124"  # curl_cffi convenience for User-Agent spoofing
    )
    resp.raise_for_status()
    return resp.text


def put_ua_in_header() -> dict[str, str]:
    ua = get_ua()
    return {
        **base_headers,
        "User-Agent": ua,
    }


def strip_json_beginning(raw_text: str):
    # raw_text is already the response body
    if raw_text.startswith("{}&&"):
        raw_text = raw_text.split("&&", 1)[1]
    return json.loads(raw_text)