import time
import random
from playwright.sync_api import sync_playwright
from user_agents import get_ua
from bs4 import BeautifulSoup
from curl_cffi import requests
import re
import json


# base_headers = {
#     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
#     "Accept-Language": "en",
#     "Cache-Control": "no-cache",
#     "Pragma": "no-cache",
#     "Sec-Ch-Ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
#     "Sec-Ch-Ua-Mobile": "?0",
#     "Sec-Ch-Ua-Platform": '"Windows"',
#     "Sec-Fetch-Dest": "document",
#     "Sec-Fetch-Mode": "navigate",
#     "Sec-Fetch-Site": "none",
#     "Sec-Fetch-User": "?1",
#     "Upgrade-Insecure-Requests": "1",
# }

base_headers = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "en-US,en;q=0.9",
    "cache-control": "max-age=0",
    "priority": "u=0, i",
    # "referer": "https://www.zillow.com/rental-manager/price-my-rental/results/4545-s-ellesmere-st-gilbert-az-85297/",
    "sec-ch-ua": 'Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "macOS",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
}


def get_zestimate(address, city, state, zipcode):
    url = create_url(address, city, state, zipcode)
    html = fetch_html_via_https(url)
    return pull_zestimate_from_html(html)


def create_url(address, city, state, zipcode):
    address = address.replace(" ", "-")
    address = address.lower()
    city = city.lower()
    state = state.lower()
    return f"https://www.zillow.com/rental-manager/price-my-rental/results/{address}-{city}-{state}-{zipcode}/"


def pull_zestimate_from_html(html: str):
    soup = BeautifulSoup(html, "html.parser")
    # find the <script> that contains our INITIAL_STATE
    for script in soup.find_all("script", {"type":"text/javascript"}):
        text = script.get_text()
        if "window.__INITIAL_STATE__" in text:
            # capture everything between the first `{` after the = and the matching `}`
            m = re.search(
                r"window\.__INITIAL_STATE__\s*=\s*({.*?})\s*;\s*$",
                text,
                flags=re.DOTALL
            )
            if not m:
                raise ValueError("Found the script tag, but regex didn’t match.")
            payload = m.group(1)
            # convert JS `undefined` (possibly with whitespace) to JSON `null`
            payload = re.sub(r':\s*undefined', ':null', payload)

            # drop any trailing commas before `}` or `]`
            payload = re.sub(r',\s*([}\]])', r'\1', payload)
            data = json.loads(payload)
            return data["address"]["rentZestimate"], data["address"]["rentZestimateRangeHigh"], data["address"]["rentZestimateRangeLow"]

    raise ValueError("Could not find any <script> with window.__INITIAL_STATE__")


def put_ua_in_header() -> dict[str, str]:
    ua = get_ua()
    return {
        **base_headers,
        "User-Agent": ua,
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


# not currently used
def human_delay(min_ms: int = 200, max_ms: int = 1200) -> None:
    """
    Randomized sleep to mimic human-like pauses.
    """
    time.sleep(random.uniform(min_ms, max_ms) / 1000)


# not currently used
def fetch_html_for_zestimate_via_playwright(url: str, headless: bool = False, proxy: str | None = None, timeout: int = 30_000) -> str:
    with sync_playwright() as pw:
        # --- Launch browser with anti-detection flags ---
        args = [
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-infobars",
        ]
        if proxy:
            args.append(f"--proxy-server={proxy}")

        browser = pw.chromium.launch(headless=headless, args=args)

        # --- Rotating UA and randomized viewport ---
        ua = get_ua()
        viewport = {
            "width": random.choice([1200, 1280, 1366, 1440]),
            "height": random.choice([700, 768, 800, 900]),
        }
        context = browser.new_context(
            user_agent=ua,
            locale="en-US",
            timezone_id="America/Los_Angeles",
            viewport=viewport,
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "DNT": "1",
            }
        )

        # --- Stealth init script ---
        stealth_js = f"""
            // navigator.webdriver
            Object.defineProperty(navigator, 'webdriver', {{ get: () => false }});
            // languages
            Object.defineProperty(navigator, 'languages', {{ get: () => ['en-US', 'en'] }});
            // platform
            Object.defineProperty(navigator, 'platform', {{ get: () => 'Win32' }});
            // hardwareConcurrency & deviceMemory
            Object.defineProperty(navigator, 'hardwareConcurrency', {{ get: () => {random.choice([4, 8])} }});
            Object.defineProperty(navigator, 'deviceMemory', {{ get: () => {random.choice([4, 8])} }});
            // userAgentData
            Object.defineProperty(navigator, 'userAgentData', {{ get: () => ({{
                brands: [
                    {{ brand: 'Chromium', version: '114' }},
                    {{ brand: 'Google Chrome', version: '114' }}
                ],
                mobile: false
            }}) }});
            // chrome.webstore stub
            window.chrome = window.chrome || {{}};
            window.chrome.webstore = {{}};
            // plugins & mimeTypes
            Object.defineProperty(navigator, 'plugins', {{ get: () => [1,2,3,4,5] }});
            Object.defineProperty(navigator, 'mimeTypes', {{ get: () => [{{ type: 'application/pdf' }}] }});
            // permissions
            const origPerm = navigator.permissions.query;
            navigator.permissions.query = params =>
              params.name === 'notifications' ? Promise.resolve({{ state: Notification.permission }}) : origPerm(params);
            // screen dims
            Object.defineProperty(screen, 'width', {{ get: () => {viewport['width']} }});
            Object.defineProperty(screen, 'height', {{ get: () => {viewport['height']} }});
            Object.defineProperty(screen, 'colorDepth', {{ get: () => 24 }});
        """
        context.add_init_script(stealth_js)

        page = context.new_page()

        # --- Navigate & mimic human behavior ---
        page.goto(url, wait_until="networkidle", timeout=timeout)
        human_delay(500, 1500)
        page.mouse.wheel(0, random.randint(200, 500))
        human_delay(200, 600)

        # --- Wait for key element ---
        try:
            page.wait_for_selector("[data-testid='zestimate']", timeout=5000)
        except:
            pass

        human_delay(300, 800)
        html = page.content()

        # --- Cleanup ---
        context.close()
        browser.close()
        return html
