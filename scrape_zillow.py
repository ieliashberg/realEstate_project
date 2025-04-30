import json
import os
import re

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import pandas as pd

# from playwright.sync_api import sync_playwright
# from playwright_stealth import stealth_sync

# ---------------REDFIN CONSTANTS --------------------
REGION_ID = 14240
REGION_TYPE = 6

GIS_URL = "https://www.redfin.com/stingray/api/gis"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/134.0.0.0 Safari/537.36"),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.redfin.com/city/14240/AZ/Phoenix",
    "Cookie": "RF_BROWSER_ID=YvfK7f_bRImqh0uclGWpRA; RF_BROWSER_ID_GREAT_FIRST_VISIT_TIMESTAMP=2025-04-28T22%3A10"
              "%3A29.855466; RF_BID_UPDATED=1; __pdst=4d9ac50f65e04fd5a3b79540489d6d69; "
              "_fbp=fb.1.1745903430261.97759116252689094; _scor_uid=2f78d4133da24378bbd591041a2e3fe2; "
              "OTGPPConsent=DBABBg~BUoAAAKA.QA; _tt_enable_cookie=1; _ttp=01JSZZ8AVE7A42A3GANVF3G2C1_.tt.1; "
              "_gid=GA1.2.496522055.1745903431; "
              "unifiedLastSearch=name%3DPhoenix%26subName%3DPhoenix%252C%2520AZ%252C%2520USA%26url%3D%252Fcity"
              "%252F14240%252FAZ%252FPhoenix%26id%3D2_14240%26type%3D2%26unifiedSearchType%3D2%26isSavedSearch%3D"
              "%26countryCode%3DUS; RF_VISITED=true; searchMode=1; sortOrder=1; sortOption=special_blend; "
              "RF_MARKET=phoenix; cw-test-20241025-floors-test-50-50=control; cw-test-20250415-req-v9=control; "
              "cw-test-stand-alone-floors-facade-hardFloor-25-25-25-25=falla; "
              "cw-test-stand-alone-floors-facade-multiplier-25-25-25-25=multo; "
              "cw-test-20250220-viewability-test=test; "
              "cw-test-stand-alone-floors-comparison-multiplier-0-100=control; "
              "OptanonAlertBoxClosed=2025-04-29T05:38:09.015Z; RF_BUSINESS_MARKET=9; "
              "ki_t=1745910534854%3B1745910534854%3B1745910534854%3B1%3B1; ki_r=; "
              "RF_LDP_VIEWS_FOR_PROMPT=%7B%22viewsData%22%3A%7B%2204-29-2025%22%3A%7B%22201850517%22%3A1%7D%7D%2C"
              "%22expiration%22%3A%222027-04-29T07%3A08%3A55.588Z%22%2C%22totalPromptedLdps%22%3A0%7D; PageCount=1; "
              "RF_LISTING_VIEWS=201850517; RF_LAST_DP_SERVICE_REGION=2606; "
              "cw-test-20250403-bidders-rise-disabled=rise-enabled; "
              "RF_LAST_USER_ACTION=1745911443079%3A8476001c5362c2e2fa44eb8ec083dea5f7a8d85e; RF_PARTY_ID=95812452; "
              "RF_AUTH=f1cc6c3d930706eb8809ebf2f65882906fb266f6; RF_W_AUTH=f1cc6c3d930706eb8809ebf2f65882906fb266f6; "
              "RF_SECURE_AUTH=a64ebf258d559512b0c2e7c7a52aac77e3e20104; JSESSIONID=CD9EEBD0748CEE4061E1D4751B0A5F27; "
              "iterableEmailCampaignId=1221221; iterableTemplateId=1803623; "
              "iterableMessageId=9476f519c3ce4a4ab9dd91f782064112; iterableEndUserId=sendm2i%40gmail.com; "
              "RF_ACCESS_LEVEL=3; shared_search_intros=1414098202%3D1745911466455%26dec%3D1745911466455%26ipc%3D1; "
              "_gcl_au=1.1.715382732.1745903431.769338865.1745911494.1745911493; RF_LAST_NAV=0; "
              "RF_LAST_ACCESS=1745955877588%3A89eb19b9b11794b154099ab8b4d5dcc62e53d0bc; "
              "_gcl_gs=2.1.k1$i1745956622$u222895640; AMP_TOKEN=%24NOT_FOUND; FEED_COUNT=%5B%221%22%2C%22t%22%5D; "
              "_gac_UA-294985-1=1.1745956623.Cj0KCQjw8cHABhC"
              "-ARIsAJnY12xSYvtUNdx3rrz_ttmMymS5l7xAaZ1ihrMw0PIhQF6RYOjrdjysPpsaAt6VEALw_wcB%2525252522%2525252522; "
              "_ga=GA1.1.872286325.1745903431; "
              "OptanonConsent=isGpcEnabled=0&datestamp=Tue+Apr+29+2025+13%3A09%3A47+GMT-0700+("
              "Pacific+Daylight+Time)&version=202403.1.0&browserGpcFlag=0&isIABGlobal=false&hosts=&consentId=2cf8f648"
              "-8a4f-454b-9e01-ce576b946d4f&interactionCount=3&isAnonUser=1&landingPath=NotLandingPage"
              "&GPPCookiesCount=1&groups=C0001%3A1%2CC0003%3A1%2CSPD_BG%3A1%2CC0002%3A1%2CC0004%3A1&AwaitingReconsent"
              "=false&geolocation=US%3BCA; "
              "userPreferences=parcels%3Dtrue%26schools%3Dfalse%26mapStyle%3Ds%26statistics%3Dtrue%26agcTooltip"
              "%3Dfalse%26agentReset%3Dfalse%26ldpRegister%3Dfalse%26afCard%3D2%26schoolType%3D0%26lastSeenLdp"
              "%3DnoSharedSearchCookie%26viewedSwipeableHomeCardsDate%3D1745957387265; "
              "_uetsid=454fa5b024b811f0950ee5635e1cf5b5; _uetvid=454fa29024b811f08a59279a7d40d126; "
              "RF_CORVAIR_LAST_VERSION=572.2.1; "
              "_gcl_aw=GCL.1745957405.Cj0KCQjw8cHABhC"
              "-ARIsAJnY12xSYvtUNdx3rrz_ttmMymS5l7xAaZ1ihrMw0PIhQF6RYOjrdjysPpsaAt6VEALw_wcB; "
              "_gcl_dc=GCL.1745957405.Cj0KCQjw8cHABhC"
              "-ARIsAJnY12xSYvtUNdx3rrz_ttmMymS5l7xAaZ1ihrMw0PIhQF6RYOjrdjysPpsaAt6VEALw_wcB; "
              "_ga_928P0PZ00X=GS1.1.1745955631.4.1.1745957404.41.0.0; "
              "__gads=ID=7d5cc3348c3d24b3:T=1745903437:RT=1745957447:S=ALNI_MaKGXNGZjyZxSRaff1gzKXPM1OLlQ; "
              "__gpi=UID=000010a35aea6fd5:T=1745903437:RT=1745957447:S=ALNI_Mb5nDr8Jd5Rl7H1A7903-SMfEemkQ; "
              "__eoi=ID=f2dcefce650d7773:T=1745903437:RT=1745957447:S=AA-AfjYTfzE1cI8hkG_kj-7iJgLd; "
              "ttcsid_C95K9BJC77U9N0P94330=1745955635377::hw7OPWUYYnJi0ReZNNdk.5.1745957551195; "
              "ttcsid=1745955635377::ihBFLn9b8gBn_OYkBQE2.5.1745957551195; "
              "aws-waf-token=bedebec2-b1a0-4828-90e9-b0a5fc82ef88:EwoAm3mMdaKqAQAA:p8hKYhHnLA4AkaiPMk75yIb48"
              "+A9IK0dhh3iz2GSMBAGzLxC2MeIlhOftDqwZj19Mb8ZUiEDpDeT+lyo7OWYPgzHh"
              "+aChRlHIfITDTNFEqQ56raPanzR8u3ImFBTlOgLj0CUL5RjGNhBIdB/K5neJt"
              "/t9M1RDL9IQFNrmtR9F1Z9AdL0bXj9DEKN2sRNZw1kyoOKURkjdwATZkdJJFmZyYScjuyPBeLpFu8DPjsv9phu08lNlsNsD4NPgd9mqgqQ8w==; RF_BROWSER_CAPABILITIES=%7B%22screen-size%22%3A2%2C%22events-touch%22%3Afalse%2C%22ios-app-store%22%3Afalse%2C%22google-play-store%22%3Afalse%2C%22ios-web-view%22%3Afalse%2C%22android-web-view%22%3Afalse%7D; _dd_s=rum=0&expire=1745958490132"
}
PARAMS = {
    "al": 3,
    "market": "phoenix",
    "mpt": 1,
    "num_homes": 350,
    "ord": "redfin-recommended-asc",
    "page_number": 1,
    "region_id": REGION_ID,  # 14240
    "region_type": REGION_TYPE,  # 6
    "sf": "1,2,3,5,6,7",
    "start": 0,
    "status": 9,
    "uipt": "1,2,3,4,5,6,7,8",
    "v": 8,
    "zoomLevel": 7
}


def fetch_html_and_cookies(url, wait=5):
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

    # get cookies
    raw_cookies = driver.get_cookies()

    # grabs the full HTML
    html = driver.page_source
    driver.quit()
    return html, {c["name"]: c["value"] for c in raw_cookies}


def extract_total_from_html(html: str) -> int:
    """
    Parses the initial search-results HTML to find the total homes count, e.g. "6,500 homes".
    """
    soup = BeautifulSoup(html, "html.parser")
    # Try the common span selector
    el = soup.select_one("span.homeFilterHeader-count")
    if el:
        text = el.get_text(strip=True)  # e.g. "6,500"
        return int(text.replace(",", ""))
    # Fallback: regex search
    m = re.search(r"of ([\d,]+) homes", html)
    if m:
        return int(m.group(1).replace(",", ""))
    raise RuntimeError("Could not find total homes count in HTML")


def fetch_all_listings(html: str, url) -> list:
    """
    Paginates through the GIS endpoint, de-duplicates overlapping results,
    and stops when reaching the UI-reported total count.
    """
    total_homes = 6249  # extract_total_from_html(html)
    print(f"Total homes reported by UI: {total_homes}")

    seen_ids = set()
    all_homes = []

    while True:
        if PARAMS["page_number"] != 1:
            HEADERS["Referer"] = f"{url}/page-{PARAMS['page_number'] - 1}"
        print("Referer = " + HEADERS["Referer"])
        print("Current page number: " + str(PARAMS['page_number']))

        resp = requests.get(GIS_URL, params=PARAMS, headers=HEADERS, timeout=15)
        raw = resp.text
        if raw.startswith("{}&&"):
            raw = raw.split("&&", 1)[1]
        obj = json.loads(raw)
        payload = obj.get("payload", {})
        batch = payload.get("homes", [])

        # Deduplicate
        new_count = 0
        for home in batch:
            lid = home.get("listingId") or home.get("homeId")
            if lid and lid not in seen_ids:
                seen_ids.add(lid)
                all_homes.append(home)
                new_count += 1

        print(f"Batch start={PARAMS['start']}: returned {len(batch)}, new {new_count}, total unique {len(all_homes)}")

        # Stop if no new homes or reached UI total
        if new_count == 0:
            print("No new homes in this batch. Ending pagination.")
            break
        if len(all_homes) >= total_homes:
            print("Reached the UI-reported total. Ending pagination.")
            break

        # Advance or finish
        if len(batch) < 350:
            print("Final partial batch received. Ending pagination.")
            break

        PARAMS["page_number"] += 1
        time.sleep(1)

    return all_homes


def save_to_csv(homes: list, out_path: str = "redfin_homes.csv"):
    """Convert listings to a DataFrame and save."""
    df = pd.DataFrame([{
        "listingId": h.get("listingId") or h.get("homeId"),
        "address": h.get("address"),
        "price": h.get("price"),
        "beds": h.get("beds"),
        "baths": h.get("baths"),
        "sqft": h.get("sqft"),
        "latitude": h.get("latLong", {}).get("latitude"),
        "longitude": h.get("latLong", {}).get("longitude"),
    } for h in homes])
    df.to_csv(out_path, index=False)
    print(f"Saved {len(df)} listings to {out_path}")


def fetch_redfin_gis_url_with_debug():
    # ─── SETUP ───────────────────────────────────────────────────────
    os.makedirs("debug_screenshots", exist_ok=True)

    options = Options()
    # enable performance logging so we can read the network events
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    options.add_experimental_option("perfLoggingPrefs", {"enableNetwork": True})
    # options.add_argument("--headless=new")  # once you verify it works

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    wait = WebDriverWait(driver, 20)

    try:
        # ─── 1) NAVIGATE & INITIAL SCREENSHOTS ─────────────────────────
        driver.get("https://www.redfin.com/city/14240/AZ/Phoenix")
        time.sleep(5)  # let all JS & map tiles load

        # full-page screenshot
        driver.save_screenshot("debug_screenshots/01-full-page.png")
        print("✅ Saved full-page screenshot -> debug_screenshots/01-full-page.png")

        map_wrap = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#search-map-wrapper")))
        driver.execute_script("arguments[0].scrollIntoView(true);", map_wrap)
        ActionChains(driver).move_to_element(map_wrap).perform()
        time.sleep(2)

        # ─── 4) DUMP CONTROLS (optional DEBUG) ─────────────────────────
        try:
            controls = driver.find_element(By.CSS_SELECTOR, ".bp-MapControls__mainControls")
            print("Controls aria-hidden:", controls.get_attribute("aria-hidden"))
            controls.screenshot("debug_screenshots/03-controls.png")

        except:
            print("Couldn’t screenshot controls; maybe selector changed")

        zoom_minus = wait.until(EC.element_to_be_clickable((
            By.CSS_SELECTOR, '[data-rf-test-id="map-zoom-control-minus"] button'
        )))
        zoom_minus.click()
        print("🔍 Clicked zoom-out button")
        time.sleep(3)

        # ─── 5) DUMP & SCAN PERFORMANCE LOGS ──────────────────────────
        perf_entries = driver.get_log("performance")
        with open("debug_screenshots/perf-logs.jsonl", "w") as f:
            for entry in perf_entries:
                f.write(json.dumps(entry) + "\n")
        print("✅ Wrote performance log entries -> debug_screenshots/perf-logs.jsonl")

        for entry in perf_entries:
            msg = json.loads(entry["message"])["message"]
            if msg.get("method") == "Network.requestWillBeSent":
                url = msg["params"]["request"]["url"]
                if "/stingray/api/gis" in url:
                    print("🎯 Found GIS URL:", url)
                    return url

        raise RuntimeError("No GIS call fired. Check your screenshots & perf-logs.")

    finally:
        driver.quit()


def main():
    # if I just want to read from a csv file listed at the bottom of the redfin page
    # df = pd.read_csv("redfin_phoenix_data.csv")
    # print(df.head())

    # url = "https://www.redfin.com/city/14240/AZ/Phoenix"
    #
    # # extract html and cookies (if necessary)
    # html, cookies = fetch_html_and_cookies(url, 5)
    # with open("html.txt", "w", newline="", encoding="utf-8") as f:
    #     f.write(html)
    #
    # # all_listings = fetch_all_listings(html, url)
    # # save_to_csv(all_listings)

    try:
        gis_url = fetch_redfin_gis_url_with_debug()
        print("🔗 Found GIS URL:\n", gis_url)
    except Exception as e:
        print("⚠️ Error:", e)


if __name__ == "__main__":
    main()
