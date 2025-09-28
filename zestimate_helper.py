from dataBase import Property, Zestimate_History, SessionLocal
import time
import random
from playwright.sync_api import sync_playwright
from services.user_agent_service import UserAgentService
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from utils.http_utils import fetch_html_via_https, ZILLOW_HEADERS as zillow_base_headers
import re
import json
import logging

zestimate_update_buffer = 0

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_zestimate(address, city, state, zipcode):
    """Get zestimate data for a property from Zillow."""
    try:
        url = create_url(address, city, state, zipcode)
        
        # Try HTTP request first
        html = _try_http_request(url)
        
        # If HTTP failed, try Playwright
        if not html:
            html = _try_playwright_request(url)
        
        # Check if we got valid HTML
        if not html:
            logger.error(f"ZILLOW FAILED: No HTML received from HTTP or Playwright for {address}, {city}, {state} {zipcode} - URL: {url}")
            return None, None, None
            
        is_valid = _is_valid_zestimate_page(html, url)
        if not is_valid:
            logger.error(f"ZILLOW FAILED: Invalid page (no rentzestimate data) for {address}, {city}, {state} {zipcode} - URL: {url}")
            return None, None, None
        
        # Parse zestimate data from HTML
        try:
            result = pull_zestimate_from_html(html)
            zestimate, high, low = result
            if zestimate is not None:
                high_str = f"${high:,}" if high is not None else "None"
                low_str = f"${low:,}" if low is not None else "None"
                logger.info(f"ZILLOW SUCCESS: {address}, {city}, {state} {zipcode} - Zestimate: ${zestimate:,}, High: {high_str}, Low: {low_str}")
            else:
                logger.warning(f"ZILLOW NO DATA: {address}, {city}, {state} {zipcode} - Property has no zestimate data available - URL: {url}")
            return result
        except Exception as parse_error:
            logger.error(f"ZILLOW FAILED: Could not parse zestimate data for {address}, {city}, {state} {zipcode} - {type(parse_error).__name__}: {parse_error} - URL: {url}")
            return None, None, None
        
    except Exception as e:
        logger.error(f"ZILLOW FAILED: Exception for {address}, {city}, {state} {zipcode} - {type(e).__name__}: {e} - URL: {url}")
        return None, None, None


def _try_http_request(url):
    """Try to fetch HTML using HTTP request."""
    try:
        html = fetch_html_via_https(url, zillow_base_headers)
        if html and _is_valid_zestimate_page(html, url):
            return html
        return None
    except Exception as e:
        return None


def _try_playwright_request(url):
    """Try to fetch HTML using Playwright."""
    try:
        html = fetch_with_retries_via_playwright(url)
        if html and _is_valid_zestimate_page(html, url):
            return html
        return None
    except Exception as e:
        return None


def create_url(address, city, state, zipcode):
    """Create Zillow rental manager URL from address components."""
    if not all([address, city, state, zipcode]):
        raise ValueError("All address components (address, city, state, zipcode) are required")
    
    # Clean and format address components
    clean_address = address.strip().replace(" ", "-").lower()
    clean_address = re.sub(r'#', '', clean_address)
    clean_city = city.strip().lower()
    clean_state = state.strip().lower()
    clean_zipcode = str(zipcode).strip()
    
    return f"https://www.zillow.com/rental-manager/price-my-rental/results/{clean_address}-{clean_city}-{clean_state}-{clean_zipcode}/"


def pull_zestimate_from_html(html: str):
    """Extract zestimate data from Zillow HTML page."""
    if not html or not html.strip():
        raise ValueError("Empty HTML provided")
    
    soup = BeautifulSoup(html, "html.parser")
    
    # Find the script tag that contains INITIAL_STATE
    script_tags = soup.find_all("script", {"type": "text/javascript"})
    if not script_tags:
        script_tags = soup.find_all("script")  # Fallback to all script tags
    
    for script in script_tags:
        text = script.get_text()
        if "window.__INITIAL_STATE__" in text:
            # Capture everything between the first `{` after the = and the matching `}`
            match = re.search(
                r"window\.__INITIAL_STATE__\s*=\s*({.*?})\s*;\s*$",
                text,
                flags=re.DOTALL
            )
            if not match:
                logger.warning("Found script tag with INITIAL_STATE but regex didn't match")
                continue
                
            payload = match.group(1)
            
            # Convert JS `undefined` (possibly with whitespace) to JSON `null`
            payload = re.sub(r':\s*undefined', ':null', payload)
            
            # Drop any trailing commas before `}` or `]`
            payload = re.sub(r',\s*([}\]])', r'\1', payload)
            
            try:
                data = json.loads(payload)
                
                # Extract zestimate data with error handling
                address_data = data.get("address", {})
                zestimate = address_data.get("rentZestimate")
                zestimate_high = address_data.get("rentZestimateRangeHigh")
                zestimate_low = address_data.get("rentZestimateRangeLow")
                
                # Return the values even if zestimate is None - this is valid for properties without zestimate data
                return zestimate, zestimate_high, zestimate_low
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON payload: {e}")
                continue
    
    raise ValueError("Could not find any <script> with window.__INITIAL_STATE__ containing valid zestimate data")


def upsert_zestimates(session, property_id, zestimate, zestimate_high, zestimate_low):
    """Update property zestimate values and create history record if values changed."""
    corresponding_property = (
        session
        .query(Property)
        .filter_by(property_id=property_id)
        .first()
    )
    
    if not corresponding_property:
        logger.error(f"Property with ID {property_id} not found")
        return
    
    old_zestimate = corresponding_property.current_zestimate
    old_zestimate_high = corresponding_property.current_zestimate_high
    old_zestimate_low = corresponding_property.current_zestimate_low
    
    values_changed = False

    # Update zestimate if it changed significantly
    if zestimate is not None and (old_zestimate is None or abs(old_zestimate - zestimate) > zestimate_update_buffer):
        corresponding_property.current_zestimate = zestimate
        if old_zestimate is None:
            logger.info(f"DATABASE ADD: Property {property_id} - Added zestimate: ${zestimate:,}")
        else:
            logger.info(f"DATABASE UPDATE: Property {property_id} - Zestimate changed from ${old_zestimate:,} to ${zestimate:,}")
        values_changed = True

    # Update zestimate_high if it changed significantly
    if zestimate_high is not None and (old_zestimate_high is None or abs(old_zestimate_high - zestimate_high) > zestimate_update_buffer):
        corresponding_property.current_zestimate_high = zestimate_high
        if old_zestimate_high is None:
            logger.info(f"DATABASE ADD: Property {property_id} - Added zestimate_high: ${zestimate_high:,}")
        else:
            logger.info(f"DATABASE UPDATE: Property {property_id} - Zestimate_high changed from ${old_zestimate_high:,} to ${zestimate_high:,}")
        values_changed = True

    # Update zestimate_low if it changed significantly
    if zestimate_low is not None and (old_zestimate_low is None or abs(old_zestimate_low - zestimate_low) > zestimate_update_buffer):
        corresponding_property.current_zestimate_low = zestimate_low
        if old_zestimate_low is None:
            logger.info(f"DATABASE ADD: Property {property_id} - Added zestimate_low: ${zestimate_low:,}")
        else:
            logger.info(f"DATABASE UPDATE: Property {property_id} - Zestimate_low changed from ${old_zestimate_low:,} to ${zestimate_low:,}")
        values_changed = True

    # Create history record if any values changed
    if values_changed:
        new_zestimate_row = Zestimate_History(
            property_id=property_id,
            zestimate=zestimate,
            zestimate_low=zestimate_low,
            zestimate_high=zestimate_high,
            date_retrieved=datetime.now(timezone.utc)
        )
        session.add(new_zestimate_row)
        session.flush()
        logger.info(f"DATABASE INSERT: Property {property_id} - Created zestimate history record")
    else:
        logger.info(f"DATABASE NO CHANGE: Property {property_id} - Zestimate values unchanged")


def human_delay(min_ms: int = 200, max_ms: int = 1200) -> None:
    """
    Randomized sleep to mimic human-like pauses.
    """
    time.sleep(random.uniform(min_ms, max_ms) / 1000)


def _is_valid_zestimate_page(html: str, url: str = None) -> bool:
    """
    Check if the HTML content contains zestimate data.
    Returns True if the page contains 'rentzestimate' (valid page).
    Returns False if the page doesn't contain 'rentzestimate' (captcha/error page).
    """
    if not html or not html.strip():
        return False
    
    html_lower = html.lower()
    return 'rentzestimate' in html_lower


def _get_browser_args(proxy: str | None = None) -> list[str]:
    """Get browser arguments for stealth mode."""
    args = [
        "--disable-blink-features=AutomationControlled",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-infobars",
        "--disable-gpu",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-web-security",
        "--disable-features=VizDisplayCompositor",
        "--disable-extensions",
        "--disable-plugins",
        "--disable-default-apps",
        "--disable-sync",
        "--disable-translate",
        "--hide-scrollbars",
        "--mute-audio",
        "--disable-background-timer-throttling",
        "--disable-renderer-backgrounding",
        "--disable-backgrounding-occluded-windows",
        "--disable-client-side-phishing-detection",
        "--disable-component-extensions-with-background-pages",
        "--disable-hang-monitor",
        "--disable-prompt-on-repost",
        "--disable-sync-preferences",
        "--disable-domain-reliability",
        "--disable-features=TranslateUI",
        "--disable-ipc-flooding-protection",
        "--disable-features=AutomationControlled",
        "--exclude-switches=enable-automation",
    ]
    
    if proxy:
        args.append(f"--proxy-server={proxy}")
    
    return args


def _get_random_user_agent() -> str:
    """Get a random working user agent from the database."""
    try:
        session = SessionLocal()
        ua_service = UserAgentService(session)
        user_agents = ua_service.get_working_user_agents(1)
        session.close()
        return user_agents[0] if user_agents else "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    except Exception as e:
        logger.warning(f"Failed to get user agent from database: {e}")
        return "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def _get_random_viewport() -> dict:
    """Get a random viewport size."""
    return {
        "width": random.choice([1200, 1280, 1366, 1440]),
        "height": random.choice([700, 768, 800, 900]),
    }


def fetch_html_for_zestimate_via_playwright(url: str, headless: bool = True, proxy: str | None = None, timeout: int = 30_000) -> str:
    """Fetch HTML from Zillow using Playwright with stealth settings."""
    with sync_playwright() as pw:
        # Launch browser with stealth settings
        browser_args = _get_browser_args(proxy)
        browser = pw.chromium.launch(headless=headless, args=browser_args)

        # Set up user agent and viewport
        user_agent = _get_random_user_agent()
        viewport = _get_random_viewport()
        context = browser.new_context(
            user_agent=user_agent,
            locale="en-US",
            timezone_id="America/Los_Angeles",
            viewport=viewport,
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "DNT": "1",
            }
        )

        # --- Enhanced stealth init script ---
        stealth_js = f"""
            // Remove webdriver traces
            Object.defineProperty(navigator, 'webdriver', {{ get: () => undefined }});
            delete navigator.__proto__.webdriver;
            
            // Override automation indicators
            Object.defineProperty(navigator, 'plugins', {{
                get: () => {{
                    return {{
                        0: {{ name: 'Chrome PDF Plugin', description: 'Portable Document Format', filename: 'internal-pdf-viewer' }},
                        1: {{ name: 'Chrome PDF Viewer', description: '', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' }},
                        2: {{ name: 'Native Client', description: '', filename: 'internal-nacl-plugin' }},
                        length: 3
                    }};
                }}
            }});
            
            Object.defineProperty(navigator, 'languages', {{ get: () => ['en-US', 'en'] }});
            Object.defineProperty(navigator, 'platform', {{ get: () => 'Win32' }});
            Object.defineProperty(navigator, 'hardwareConcurrency', {{ get: () => {random.choice([4, 8, 12])} }});
            Object.defineProperty(navigator, 'deviceMemory', {{ get: () => {random.choice([4, 8, 16])} }});
            
            // Override userAgentData
            Object.defineProperty(navigator, 'userAgentData', {{ 
                get: () => ({{
                    brands: [
                        {{ brand: 'Not_A Brand', version: '8' }},
                        {{ brand: 'Google Chrome', version: '120' }},
                        {{ brand: 'Chromium', version: '120' }}
                    ],
                    mobile: false,
                    platform: 'Windows'
                }})
            }});
            
            // Chrome object
            window.chrome = {{
                runtime: {{}},
                loadTimes: function() {{}},
                csi: function() {{}},
                app: {{}}
            }};
            
            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({{ state: Notification.permission }}) :
                    originalQuery(parameters)
            );
            
            // Screen properties
            Object.defineProperty(screen, 'width', {{ get: () => {viewport['width']} }});
            Object.defineProperty(screen, 'height', {{ get: () => {viewport['height']} }});
            Object.defineProperty(screen, 'colorDepth', {{ get: () => 24 }});
            Object.defineProperty(screen, 'pixelDepth', {{ get: () => 24 }});
            
            // Remove automation indicators
            Object.defineProperty(navigator, 'permissions', {{
                get: () => {{
                    const originalPermissions = navigator.permissions;
                    const query = originalPermissions.query.bind(originalPermissions);
                    originalPermissions.query = (params) => {{
                        if (params.name === 'notifications') {{
                            return Promise.resolve({{ state: 'default' }});
                        }}
                        return query(params);
                    }};
                    return originalPermissions;
                }}
            }});
            
            // Override getParameter to hide automation
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {{
                if (parameter === 37445) {{
                    return 'Intel Inc.';
                }}
                if (parameter === 37446) {{
                    return 'Intel Iris OpenGL Engine';
                }}
                return getParameter(parameter);
            }};
            
            // Mock realistic timing
            const start = Date.now();
            Object.defineProperty(performance, 'timing', {{
                get: () => {{
                    const now = Date.now();
                    return {{
                        navigationStart: start,
                        loadEventEnd: now - {random.randint(100, 500)},
                        domContentLoadedEventEnd: now - {random.randint(50, 200)}
                    }};
                }}
            }});
        """
        context.add_init_script(stealth_js)

        page = context.new_page()

        # --- Navigate with realistic behavior ---
        try:
            # Add random delay before navigation
            human_delay(500, 2000)
            
            # Navigate to page
            response = page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            
            # Check if we got blocked immediately
            if response and response.status >= 400:
                logger.warning(f"Got HTTP {response.status} for {url}")
                return page.content()
            
            # Simulate realistic mouse movement
            for _ in range(random.randint(5, 12)):
                x = random.randint(50, viewport['width'] - 50)
                y = random.randint(50, viewport['height'] - 50)
                page.mouse.move(x, y, steps=random.randint(8, 20))
                time.sleep(random.uniform(0.1, 0.8))
            
            # Random scrolling
            for _ in range(random.randint(2, 5)):
                page.mouse.wheel(0, random.randint(200, 1000))
                human_delay(200, 800)
            
            # Wait for page to load and check for captcha
            try:
                # Wait a bit for any dynamic content
                page.wait_for_timeout(random.randint(2000, 5000))
                
                # Check if we got a valid zestimate page
                html = page.content()
                if not _is_valid_zestimate_page(html, url):
                    logger.warning(f"Detected invalid page for {url}")
                    return html
                
                # Try to wait for zestimate element if it exists
                try:
                    page.wait_for_selector("[data-testid='zestimate']", timeout=3000)
                except:
                    # Element not found, but that's ok - we'll parse what we have
                    pass
                    
            except Exception as e:
                logger.warning(f"Error during page interaction: {e}")
                html = page.content()
                
        except Exception as e:
            logger.error(f"Navigation failed for {url}: {e}")
            html = page.content()
        
        # Log the received HTML for debugging
        logger.info(f"Received HTML from {url}: {len(html)} characters")
        logger.debug(f"HTML preview (first 300 chars): {html[:300]}")
        
        # Check for common indicators in the HTML
        html_lower = html.lower()
        if 'zestimate' in html_lower:
            logger.info(f"HTML contains 'zestimate' - likely a valid Zillow page")
        if 'zillow' in html_lower:
            logger.info(f"HTML contains 'zillow' - likely a valid Zillow page")
        if 'error' in html_lower and '404' in html_lower:
            logger.warning(f"HTML appears to be a 404 error page")
        if 'blocked' in html_lower or 'forbidden' in html_lower:
            logger.warning(f"HTML appears to indicate blocking/forbidden access")

        cookie_list = context.cookies()
        cookie_string = cookies_list_to_header(cookie_list)

        zillow_base_headers["cookie"] = cookie_string

        time.sleep(60)

        # --- Cleanup ---
        context.close()
        browser.close()
        logger.debug(html)
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


def fetch_with_retries_via_playwright(url: str, max_attempts: int = 3, base_backoff: float = 2.0) -> str:
    """
    Try to fetch Zillow page with retries and exponential backoff.
    Retries if we get captcha pages or network errors.
    """
    last_exception = None
    last_html = None

    for attempt in range(1, max_attempts + 1):
        try:
            logger.info(f"Attempt {attempt}/{max_attempts} for {url}")
            
            # Vary headless mode and add delays between attempts
            headless = attempt <= 1  # Try headless on first attempt, headful on retries
            html = fetch_html_for_zestimate_via_playwright(url, headless=headless, timeout=15000)

            # Check if we got a valid zestimate page
            if not _is_valid_zestimate_page(html, url):
                logger.warning(f"Attempt {attempt}: Got invalid page")
                last_html = html
                if attempt < max_attempts:
                    # Exponential backoff with jitter
                    backoff = base_backoff ** attempt + random.uniform(1, 3)
                    logger.info(f"Waiting {backoff:.1f} seconds before retry...")
                    time.sleep(backoff)
                    continue
                else:
                    logger.error(f"All attempts failed - got invalid page on final attempt")
                    return html
            else:
                logger.info(f"Successfully fetched page on attempt {attempt}")
                return html

        except Exception as exc:
            last_exception = exc
            logger.warning(f"Attempt {attempt}/{max_attempts} failed: {exc!r}")
            if attempt < max_attempts:
                # Exponential backoff with jitter
                backoff = base_backoff ** attempt + random.uniform(1, 3)
                logger.info(f"Waiting {backoff:.1f} seconds before retry...")
                time.sleep(backoff)
                continue
            else:
                logger.error(f"All {max_attempts} attempts failed for URL: {url}")
                raise last_exception

    # Should never reach here
    return last_html or ""
