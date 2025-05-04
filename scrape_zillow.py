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

from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync


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


def click_more_property_data_and_fetch_page_html(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/135.0.0.0 Safari/537.36"
            )
        )

        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded")

        # wait for redfin to load in the button if it's there
        time.sleep(1)

        property_history_div = page.query_selector("div.sectionContainer[data-rf-test-id='propertyHistory']")
        if property_history_div:
            btn = property_history_div.query_selector("button.ExpandableLink.clickable")
            if btn:
                btn.click()
            else:
                print("No ExpandableLink button in history section")
        else:
            print("No propertyHistory section on this page")

        html = page.content()
        browser.close()
        return html


def fetch_gis_url_headers_and_json(page_url):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/135.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        # 1) Navigate until network is quiet
        page.goto(page_url)
        time.sleep(1)

        # 2) Prepare to catch the GIS response
        #    The lambda will be evaluated on every response: we pick the one whose URL contains "/stingray/api/gis"
        with page.expect_response(lambda response: "/stingray/api/gis?" in response.url, timeout=10_000) as resp_info:
            # 3) Trigger the map‐refresh that fires that request
            page.click("[data-rf-test-id='map-zoom-control-minus'] button")
        gis_response = resp_info.value

        # 4) Pull out URL, request headers, and JSON body
        gis_url = gis_response.url
        gis_headers = gis_response.request.headers
        raw_text = gis_response.text()
        if raw_text.startswith("{}&&"):
            raw_text = raw_text.split("&&", 1)[1]
        gis_payload = json.loads(raw_text)

        browser.close()
        return gis_url, gis_headers, gis_payload


# not currently being used
def get_cookies_from_driver(driver) -> dict:
    return {c["name"]: c["value"] for c in driver.get_cookies()}


# not currently being used
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


# not currently being used
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


# not currently being used
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


# not currently being used
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
            "monthly hoa": h.get("hoa", {}).get("value"),
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
            "dom": h.get("dom", {}).get("value"),
            "listingAgentName": h.get("listingAgent", {}).get("name"),
            "listingAgentRedfinId": h.get("listingAgent", {}).get("redfinAgentId"),
            "url": "https://www.redfin.com" + h.get("url"),
            "isNewConstruction": h.get("isNewConstruction"),
            "listingRemarks": h.get("listingRemarks"),
            "businessMarketId": h.get("businessMarketId"),
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
        html = click_more_property_data_and_fetch_page_html(url)
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

            # description
            description = history_row.select_one("div.description-col.col-4 > div").get_text(strip=True)

            # price
            price = history_row.select_one("div.price-col.number").get_text(strip=True)

            print(f"date = {date}")
            print(f"description = {description}")
            print(f"price = {price}")

        # get last year tax information
        tax_label_node = soup.find(string="Tax Annual Amount: ")
        if tax_label_node:
            tax_amount_span = tax_label_node.find_next("span")
            df.loc[i, 'Tax Annual Amount'] = tax_amount_span.text

        # get the listing agent(s)
        agents = soup.find_all("span", class_="agent-basic-details--heading")
        for agent in agents:
            agent_name = agent.find("span").get_text(strip=True)
            print(agent_name)

        agents = soup.find_all("div", class_="agent-info-item flex flex-wrap")
        for agent in agents:
            agent_name = agent.find("span", class_="agent-basic-details--heading").find("span").get_text(strip=True)
            full_broker_text = soup.select_one("span.agent-basic-details--broker > span").get_text(strip=True)
            agent_broker = full_broker_text.replace("•", "").strip()  # remove the dot and trim
            print(agent_name)
            print(agent_broker)

    print("updated redfin_homes.csv file")
    df.to_csv("redfin_homes.csv", index=False)


def strip_cluster_bounds_from_gis(gis_url):
    cluster_bounds_start = gis_url.find("&cluster_bounds")
    cluster_bounds_end = cluster_bounds_start + 1
    while gis_url[cluster_bounds_end] != "&":
        cluster_bounds_end += 1
    gis_without_cluster_bounds = gis_url[:cluster_bounds_start] + gis_url[cluster_bounds_end:]
    return gis_without_cluster_bounds


def main():
    # # searching a particular zip code and for no pool
    # url = "https://www.redfin.com/zipcode/85297/filter/pool-type=no-private"
    # gis_url, headers, homes_payload = fetch_gis_url_headers_and_json(url)
    # dump_homes_to_csv(homes_payload)
    get_specific_info_on_each_property('redfin_homes.csv')


if __name__ == "__main__":
    main()
