import json
import math
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


# not currently used
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


def get_cookies_from_driver(driver) -> dict:
    return {c["name"]: c["value"] for c in driver.get_cookies()}


def get_gis_request_headers(perf_entries, gis_url) -> dict:
    """
    Scans through the performance log entries for exactly the
    Network.requestWillBeSent that hit our gis_url, and returns
    its headers dict.
    """
    for entry in perf_entries:
        msg = json.loads(entry["message"])["message"]
        if msg.get("method") == "Network.requestWillBeSent":
            req = msg["params"]["request"]
            if req["url"].startswith(gis_url.split("?")[0]):
                return req["headers"]
    # fallback minimal set:
    # return {'Referer': 'https://www.redfin.com/city/14240/AZ/Phoenix', 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36', 'sec-ch-ua': '"Google Chrome";v="135", "Not-A.Brand";v="8", "Chromium";v="135"', 'sec-ch-ua-mobile': '?0', 'sec-ch-ua-platform': '"macOS"'}


def fetch_redfin_gis_url_cookies_and_header(base_url):
    options = Options()
    # enable performance logging so we can read the network events
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    options.add_experimental_option("perfLoggingPrefs", {"enableNetwork": True})
    # options.add_argument("--headless=new")  # once you verify it works

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    wait = WebDriverWait(driver, 2)

    try:
        driver.get(base_url)
        time.sleep(1)  # let all JS & map tiles load

        map_wrap = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#search-map-wrapper")))
        driver.execute_script("arguments[0].scrollIntoView(true);", map_wrap)
        ActionChains(driver).move_to_element(map_wrap).perform()
        time.sleep(1)

        zoom_minus = wait.until(EC.element_to_be_clickable((
            By.CSS_SELECTOR, '[data-rf-test-id="map-zoom-control-minus"] button'
        )))
        zoom_minus.click()
        time.sleep(2)

        # dump and scan performance logs
        perf_entries = driver.get_log("performance")
        with open("debug_screenshots/perf-logs.jsonl", "w") as f:
            for entry in perf_entries:
                f.write(json.dumps(entry) + "\n")

        gis_url = None
        gis_without_cluster_bounds = None
        for entry in perf_entries:
            msg = json.loads(entry["message"])["message"]
            if msg.get("method") == "Network.requestWillBeSent":
                url = msg["params"]["request"]["url"]
                if "/stingray/api/gis?" in url:
                    gis_url = url

                    cluster_bounds_start = gis_url.find("&cluster_bounds")
                    cluster_bounds_end = cluster_bounds_start + 1
                    while gis_url[cluster_bounds_end] != "&":
                        cluster_bounds_end += 1
                    gis_without_cluster_bounds = gis_url[:cluster_bounds_start] + gis_url[cluster_bounds_end:]

        if gis_without_cluster_bounds is not None:
            # 2) **grab your cookies from Selenium**
            cookies = get_cookies_from_driver(driver)

            # 3) **grab the exact headers Chrome used for that GIS call**
            headers = get_gis_request_headers(perf_entries, gis_url)

            return gis_without_cluster_bounds, cookies, headers

        raise RuntimeError("No GIS call fired. Check your screenshots & perf-logs.")
    finally:
        driver.quit()


# don't need to use this if only 1 page
def increment_page_number_and_start_in_gis(currGis):
    # get the beginning of the pageNum
    pageNum_begin_ndx = currGis.find("page_number=")
    pageNum_begin_ndx += len("page_number=")

    # iterate linearly until you get a & signifying the end of pageNum param
    pageNum_end_ndx = pageNum_begin_ndx
    while currGis[pageNum_end_ndx] != "&":
        pageNum_end_ndx += 1
    pageNum = int(currGis[pageNum_begin_ndx:pageNum_end_ndx])

    # same thing as pageNum
    start_begin_ndx = currGis.find("start=")
    start_begin_ndx += len("start=")
    start_end_ndx = start_begin_ndx
    while currGis[start_end_ndx] != "&":
        start_end_ndx += 1
    startNum = int(currGis[start_begin_ndx:start_end_ndx])

    # increment the pageNum and startNum for the next gis
    pageNum += 1
    startNum += 350

    # convert everything back to string and return the new GIS url
    retGis = currGis[:pageNum_begin_ndx] + str(pageNum) + currGis[pageNum_end_ndx:start_begin_ndx] + str(
        startNum) + currGis[start_end_ndx:]
    return retGis


def get_homes_data(gis_url, cookies, headers):
    session = requests.Session()
    session.headers.update(headers)
    # Bulk‐load the cookies you grabbed from Selenium into the session
    for name, val in cookies.items():
        session.cookies.set(name, val, domain=".redfin.com")

    # strip the {}&& from the json file and then convert it all to json. then return
    resp = session.get(gis_url, timeout=15)
    text = resp.text
    if text.startswith("{}&&"):
        text = text.split("&&", 1)[1]

    data = json.loads(text)
    with open("redfin_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return data


def list_to_json_str(x):
    """ Turn any list (of primitives or dicts) into a compact JSON string """
    if isinstance(x, list):
        return json.dumps(x, separators=(",", ":"), ensure_ascii=False)
    return x


def dump_homes_to_csv(full_homes_json):
    homes_list = []
    homes = full_homes_json.get("payload", {}).get("homes", [])
    if not homes:
        raise RuntimeError("No homes found in your JSON")

    for h in homes:
        currHome = {
            "mlsId": h.get("mlsId", {}).get("value"),
            "mlsStatus": h.get("mlsStatus"),
            "price": h.get("price", {}).get("value"),
            "hideSalePrice": h.get("hideSalePrice"),
            "hoa": h.get("hoa", {}).get("value"),
            "sqFt": h.get("sqFt", {}).get("value"),
            "pricePerSqFt": h.get("pricePerSqFt", {}).get("value"),
            "lotSize": h.get("lotSize", {}).get("value"),
            "beds": h.get("beds"),
            "baths": h.get("baths"),
            "location": h.get("location", {}).get("value"),
            "stories": h.get("stories"),
            "latitude": h.get("latLong", {}).get("value", {}).get("latitude"),
            "longitude": h.get("latLong", {}).get("value", {}).get("longitude"),
            "streetLine": h.get("streetLine", {}).get("value"),
            "unitNumber": h.get("unitNumber", {}).get("value"),
            "city": h.get("city"),
            "state": h.get("state"),
            "zip": h.get("zip"),
            "postalCode": h.get("postalCode", {}).get("value"),
            "countryCode": h.get("countryCode"),
            "soldDate": h.get("soldDate"),
            "yearBuilt": h.get("yearBuilt", {}).get("value"),
            "dom": h.get("dom"),
            "listingAgentName": h.get("listingAgent", {}).get("name"),
            "listingAgentRedfinId": h.get("listingAgent", {}).get("redfinAgentId"),
            "url": "https://www.redfin.com" + h.get("url"),
            "isNewConstruction": h.get("isNewConstruction"),
            "listingRemarks": h.get("listingRemarks"),
            "businessMarketId": h.get("businessMarketId"),
            "remarksAccessLevel": h.get("remarksAccessLevel"),
            "propertyType": h.get("propertyType"),
            "listingType": h.get("listingType"),
            "propertyId": h.get("propertyId"),
            "listingId": h.get("listingId"),
            "dataSourceId": h.get("dataSourceId"),
            "marketId": h.get("marketId"),
            "searchStatus": h.get("searchStatus")
        }
        homes_list.append(currHome)

    # write out homes to redfin_homes.csv
    df = pd.DataFrame(homes_list)
    df.to_csv("redfin_homes.csv", index=False)
    print(f"Saved {len(df)} rows to redfin_homes.csv")


def get_specific_info_on_each_property(data_csv):
    df = pd.read_csv(data_csv)

    # add new necessary columns
    df['Tax Annual Amount'] = None
    df['covered spaces'] = None

    for i, row in df.iterrows():

        url = df.iloc[i]['url']
        html, cookies = fetch_html_and_cookies(url)
        # with open('html.txt', 'w', encoding='utf-8') as f:
        #     f.write(html)
        #
        # with open('html.txt', 'r', encoding='utf-8') as f:
        #     html = f.read()

        soup = BeautifulSoup(html, "html.parser")

        # find the outer school table container:
        schools_container = soup.find("div", class_="schools-content")

        # within that, grab each “flex align-center” block (school):
        schools = schools_container.find_all("div", class_="flex align-center")

        # loop over each school and grab important attributes
        for school in schools:

            # get the school rating
            rating_span = school.select_one("span.rating-num.font-size-base.font-weight-bold")
            if rating_span:
                rating = rating_span.get_text(strip=True)
            else:
                rating = None
            print("rating = " + rating)
            # get the school name
            name_span = school.select_one("div.ListItem__heading.font-body-base-bold.color-text-primary")
            if name_span:
                name = name_span.get_text(strip=True)
            else:
                name = None
            print(name)

            # get the school description
            description_span = school.select_one("p.ListItem__description.font-body-small-compact.color-text-secondary")
            if description_span:
                description = description_span.get_text(strip=True)
            else:
                description = None
            print(description)

        # get the number of covered spaces
        label_node = soup.find(string="Covered Spaces: ")
        if label_node:
            covered_spaces_span = label_node.find_next("span")
            df.loc[i, 'covered spaces'] = covered_spaces_span.text

        # get the HOA info (divide by 3 if quarterly and leave it if monthly)
        label_node = soup.find(string="Association Fee: ")
        HOA_monthly_cost = 0
        if label_node:
            HOA_cost_span = label_node.find_next("span")
            HOA_monthly_cost = HOA_cost_span.text
            label_node = soup.find(string="Association Fee Frequency: ")
            if label_node:
                HOA_frequency_span = label_node.find_next("span")
                if HOA_frequency_span.text == "Quarterly":
                    HOA_monthly_cost = float(HOA_monthly_cost[1:]) / 3
        df.at[i, 'hoa'] = HOA_monthly_cost

        # get price history information (along with details)
        price_history_timeline_contents = soup.select("div.PropertyHistoryEventRow")
        for history_row in price_history_timeline_contents:

            # date
            date = history_row.select_one("div.col-4 > p").get_text(strip=True)

            # 2) description
            description = history_row.select_one("div.description-col.col-4 > div").get_text(strip=True)

            # 3) price
            price = history_row.select_one("div.price-col.number").get_text(strip=True)

            print(f"date = {date}")
            print(f"description = {description}")
            print(f"price = {price}")

        # get last year tax information
        tax_label_node = soup.find(string="Tax Annual Amount: ")
        if tax_label_node:
            tax_amount_span = tax_label_node.find_next("span")
            df.loc[i, 'Tax Annual Amount'] = tax_amount_span.text

    print("updated redfin_homes.csv file")
    df.to_csv("redfin_homes.csv", index=False)


def main():
    # # searching a particular zip code and for no pool
    url = "https://www.redfin.com/zipcode/85297/filter/pool-type=no-private"
    initial_gis_url = None
    cookies = None
    headers = None
    try:
        found_gis_url_without_cluster_bounds, found_cookies, found_headers = fetch_redfin_gis_url_cookies_and_header(
            url)

        initial_gis_url = found_gis_url_without_cluster_bounds
        cookies = found_cookies
        headers = found_headers

    except Exception as e:
        print("Error:", e)

    homes_json = get_homes_data(initial_gis_url, cookies, headers)

    # # Useful for if you don't want to run the first part every time and save the dumped json
    # with open("redfin_data.json", "r", encoding="utf-8") as f:
    #     homes_json = json.load(f)

    dump_homes_to_csv(homes_json)

    get_specific_info_on_each_property('redfin_homes.csv')
    # html, cookies = fetch_html_and_cookies(url)
    # print(html[:500])


if __name__ == "__main__":
    main()
