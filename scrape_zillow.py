import json
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time

from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync


# not currently used
def get_query_state(url: str, wait: int = 5) -> dict:
    """
    Uses Selenium+BeautifulSoup to extract the __NEXT_DATA__ JSON blob
    and returns the searchPageState.queryState dict.
    """
    options = Options()
    # options.add_argument("--headless")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.get(url)
    time.sleep(wait)
    html = driver.page_source
    driver.quit()

    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__", type="application/json")
    data = json.loads(script.string)
    return data["props"]["pageProps"]["searchPageState"]["queryState"]


# not currently used
def fetch_listings(query_state: dict, cookies: dict, referer: str, max_pages: int = 5, pause: float = 2.0) -> list:
    """
    Calls Zillow's async JSON API using the given query_state and cookies.
    Paginates through up to max_pages, pausing between calls.
    Returns a list of listing dicts.
    """
    api_url = "https://www.zillow.com/async-create-search-page-state"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/134.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": referer,
    }

    all_listings = []
    for page in range(1, max_pages + 1):
        # Update the pagination in-place
        query_state["pagination"] = {"currentPage": page}

        payload = {
            "searchQueryState": query_state,
            "wants": {
                "cat1": ["listResults", "mapResults"],
                "cat2": ["total"]
            },
            "requestId": page,
        }

        resp = requests.put(
            api_url,
            json=payload,
            headers=headers,
            cookies=cookies,
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()

        # Extract the listResults for this page
        listings = data["cat1"]["searchResults"]["listResults"]
        all_listings.extend(listings)

        # Determine how many pages exist and stop early if done
        total_pages = data["cat1"]["searchList"]["totalPages"]
        if page >= total_pages:
            break

        time.sleep(pause)

    return all_listings


# not currently used
def get_zillow_session_cookies(url: str, wait: int = 5) -> dict:
    """
    Launches Chrome via Selenium, opens the Zillow URL, waits for all JS/bot checks,
    then returns a dict of session cookies you can reuse in requests.
    """
    options = Options()
    # options.add_argument("--headless")  # uncomment to hide the browser window
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.get(url)
    time.sleep(wait)  # let PerimeterX & other scripts finish
    raw_cookies = driver.get_cookies()
    driver.quit()
    # Convert to requests-friendly format:
    return {c["name"]: c["value"] for c in raw_cookies}


def fetch_with_selenium(url, wait=5):
    # can run chrome with options (like no images or custom window size, etc)
    options = Options()
    # options.add_argument("--headless")  # uncomment once you’re happy (runs without opening chrome window)

    # locates or installs the chrome driver on this device. Service wraps the executable wo selenium can launch it
    service = Service(ChromeDriverManager().install())

    # starts a new chrome browser session
    driver = webdriver.Chrome(service=service, options=options)

    # navigates the browser to the zillow url
    driver.get(url)

    # wait until all bot checks run
    time.sleep(wait)

    # grabs the full HTML
    html = driver.page_source
    driver.quit()
    return html


def fetch_redfin_via_xhr(cookies):
    url = (
        "https://www.redfin.com/stingray/api/gis-search?"
        "al=1&market=phoenix&num_homes=350&v=2"
        "&region_id=14240&region_type=6"
    )
    headers = {
        "User-Agent": "…your browser UA…",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.redfin.com/city/14240/AZ/Phoenix"
    }
    resp = requests.get(url, headers=headers, cookies=cookies)
    resp.raise_for_status()
    payload = resp.json().get("payload", {})
    homes = payload.get("homes") or payload.get("searchResults", {}).get("homes", [])
    print(f"Got {len(homes)} homes")
    for h in homes[:5]:
        print(h.get("address"), h.get("price"))


def main():
    url = "https://www.redfin.com/city/14240/AZ/Phoenix"
    html = fetch_with_selenium(url, wait=5)
    soup = BeautifulSoup(html, "html.parser")

    # 1) Try the known attribute for Redfin's bootstrap-data
    script = soup.find("script", {"data-rf-test-id": "bootstrap-data"})

    # 2) Fallback: scan all <script> tags if that fails
    if not script:
        for s in soup.find_all("script"):
            txt = s.string or ""
            if txt.strip().startswith("{") and "homes" in txt:
                script = s
                break
        else:
            raise RuntimeError("Couldn’t locate Redfin’s JSON blob")

    # 3) Parse the JSON and inspect its top‐level keys
    data = json.loads(script.string)
    print("Top-level keys:", list(data.keys()))

    # 4) Find where the homes array lives
    #    (you’ll need to adjust this to the actual structure you see)
    homes = (
            data.get("homes") or
            data.get("searchResults", {}).get("homes") or
            data.get("payload", {}).get("homes") or
            []
    )
    print(f"Found {len(homes)} homes.")
    for h in homes[:5]:
        print(h.get("address"), h.get("price"))


if __name__ == "__main__":
    main()
