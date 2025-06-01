from dataBase import Property, Zestimate_History
import time
import random
from playwright.sync_api import sync_playwright
from user_agents import get_ua
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from http_handling_utils import fetch_html_via_https, zillow_base_headers
import re
import json
import logging

zestimate_update_buffer = 0

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_zestimate(address, city, state, zipcode):
    url = create_url(address, city, state, zipcode)
    try:
        html = fetch_html_via_https(url, zillow_base_headers)
    except Exception as e:
        logger.error(f"[ERROR] processing {url} via, trying playwright, raised {type(e).__name__}: {e}")
        html = fetch_with_retries_via_playwright(url)
        print(html)

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


def upsert_zestimates(session, property_id, zestimate, zestimate_high, zestimate_low):
    corresponding_property = (
        session
        .query(Property)
        .filter_by(property_id=property_id)
        .first()
    )
    old_zestimate = corresponding_property.current_zestimate
    old_zestimate_high = corresponding_property.current_zestimate_high
    old_zestimate_low = corresponding_property.current_zestimate_low

    if zestimate is not None and (old_zestimate is None or abs(old_zestimate - zestimate) > zestimate_update_buffer):
        corresponding_property.current_zestimate = zestimate
        logger.info("Zestimate for property {} changed to {} from {}".format(property_id, zestimate, old_zestimate))

    if zestimate_high is not None and (old_zestimate_high is None or abs(old_zestimate_high - zestimate_high) > zestimate_update_buffer):
        corresponding_property.current_zestimate_high = zestimate_high
        logger.info("Zestimate_high for property {} changed to {} from {}".format(property_id, zestimate_high, old_zestimate_high))

    if zestimate_low is not None and (old_zestimate_low is None or abs(old_zestimate_low - zestimate_low) > zestimate_update_buffer):
        corresponding_property.current_zestimate_low = zestimate_low
        logger.info("Zestimate_low for property {} changed to {} from {}".format(property_id, zestimate_low, old_zestimate_low))



        new_zestimate_row = Zestimate_History(
            property_id=property_id,
            zestimate=zestimate,
            zestimate_low=zestimate_low,
            zestimate_high=zestimate_high,
            date_retrieved=datetime.now(timezone.utc)
        )
        session.add(new_zestimate_row)
        session.flush()
        logger.info(f"Created new zestimate history row for property {property_id}")


def human_delay(min_ms: int = 200, max_ms: int = 1200) -> None:
    """
    Randomized sleep to mimic human-like pauses.
    """
    time.sleep(random.uniform(min_ms, max_ms) / 1000)


def fetch_html_for_zestimate_via_playwright(url: str, headless: bool = True, proxy: str | None = None, timeout: int = 30_000) -> str:
    with sync_playwright() as pw:
        # --- Launch browser with anti-detection flags ---
        args = [
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-infobars",
            "--disable-gpu",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ]
        if proxy:
            args.append(f"--proxy-server={proxy}")

        browser = pw.chromium.launch(headless=headless, args=args, )

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
        page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        for _ in range(random.randint(3, 7)):
            x = random.randint(100, viewport['width'] - 100)
            y = random.randint(100, viewport['height'] - 100)
            page.mouse.move(x, y, steps=random.randint(5, 15))
            time.sleep(random.uniform(0.2, 1.0))
        human_delay(300, 1500)
        page.mouse.wheel(0, random.randint(100, 800))
        human_delay(200, 600)

        # --- Wait for key element ---
        try:
            page.wait_for_selector("[data-testid='zestimate']", timeout=5000)
        except:
            pass

        human_delay(300, 800)
        html = page.content()

        cookie_list = context.cookies()
        cookie_string = cookies_list_to_header(cookie_list)

        zillow_base_headers["cookie"] = cookie_string

        time.sleep(60)

        # --- Cleanup ---
        context.close()
        browser.close()
        print(html)
        return html


def cookies_list_to_header(cookies: list[dict]) -> str:
    parts: list[str] = []
    for c in cookies:
        name = c.get("name")
        val = c.get("value", "")
        if name is None:
            continue
        # If the cookie‐value itself contains semicolons or spaces,
        # you may want to wrap it in quotes. Here we assume it's safe as-is.
        parts.append(f"{name}={val}")

    # join with “; ”
    return "; ".join(parts)


def fetch_with_retries_via_playwright(url: str, max_attempts: int = 5, backoff_seconds: float = 1.0) -> str:
    """
    Try to call `fetch_html_for_zestimate_via_playwright(url)` up to `max_attempts` times.
    Consider it a failure (and retry) if:
      - fetch_html_for_zestimate_via_playwright(...) raises any exception
      - OR the returned HTML starts with px-captcha “Access denied” HTML
    If all attempts fail, re-raise the last exception or return the last HTML (even if it’s px-captcha).
    """
    last_exception = None

    for attempt in range(1, max_attempts + 1):
        try:
            html = fetch_html_for_zestimate_via_playwright(url)

            # Normalize leading whitespace/newlines and inspect the start of the document
            start = html.lstrip()
            if start.startswith(
                    "<!DOCTYPE html><html lang=\"en\"><head>"
                    "    <meta charset=\"utf-8\">"
                    "    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
                    "    <meta name=\"description\" content=\"px-captcha\">"
            ):
                # We got the “Access denied / px-captcha” page. Treat as failure.
                raise RuntimeError("Received px-captcha “Access Denied” HTML")

            # If we reach here, fetch succeeded and it wasn’t the px‐captcha block
            return html

        except Exception as exc:
            last_exception = exc
            logger.warning(f"Attempt {attempt}/{max_attempts} failed: {exc!r}")
            if attempt < max_attempts:
                time.sleep(backoff_seconds)
                continue
            else:
                # All retries exhausted
                logger.error(f"All {max_attempts} attempts failed for URL: {url}")
                raise last_exception

    # (Should never reach here, because we either return or raise above.)
    return ""
