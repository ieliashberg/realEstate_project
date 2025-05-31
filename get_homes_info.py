from playwright.sync_api import sync_playwright, TimeoutError, Error as PlaywrightError
from dataBase import SessionLocal, Zipcodes
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta, timezone
from dateutil import parser
from user_agents import get_ua
from zestimate_helper import get_zestimate
import json
import time
import re
from curl_cffi import requests

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


def get_homes_info(url: str):
    homes_payload = fetch_homes_json(url)
    full_homes_payload = get_specific_info_on_each_property(homes_payload)
    # with open('dumps/full_homes_payload.json', 'w', encoding='utf-8') as f:
    #     # dump `data` as JSON into the file, with nice indentation
    #     json.dump(full_homes_payload, f, ensure_ascii=False, indent=2)
    return full_homes_payload


# not currently used
def extract_events(html: str):
    """
    Find the first occurrence of '"events"' in the HTML, then
    pull out the {...} that follows, sanitize it for JSON, and
    return the parsed Python object under the "events" key.
    """
    key = '"events"'
    i = html.find(key)
    if i == -1:
        raise ValueError("No 'events' key found in HTML")

    # find the first '{' after '"events":'
    brace_start = html.find("{", i)
    if brace_start == -1:
        raise ValueError("No opening brace after 'events'")

    # walk forward, counting braces, until we close the top‐level object
    depth = 0
    for j, ch in enumerate(html[brace_start:], start=brace_start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1

        # once we've closed the very first '{', j is the end
        if depth == 0:
            brace_end = j + 1
            break
    else:
        raise ValueError("Did not find matching closing brace for events object")

    raw = html[brace_start:brace_end]

    # sanitize trailing commas & JS-isms
    raw = re.sub(r",\s*([}\]])", r"\1", raw)  # drop trailing commas
    raw = re.sub(r"\bundefined\b", "null", raw)  # undefined → null

    # parse
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        snippet = raw[max(0, e.pos - 40):e.pos + 40]
        raise ValueError(f"JSON parse error at {e.pos}: …{snippet!r}") from e

    # return just the events array (or the whole object if you prefer)
    return parsed.get("events", parsed)


def fetch_homes_json(url):
    zipcode = None
    m = re.search(r"/zipcode/(\d+)", url)
    if m:
        zipcode = m.group(1)
    session = SessionLocal()
    try:
        # try the database
        record = (
            session.query(Zipcodes)
            .filter(Zipcodes.zip_code == zipcode)
            .one_or_none()
        )
        if record:
            for_sale_homes_response = fetch_html_via_https(record.for_sale_request_url)
            sold_homes_response = fetch_html_via_https(record.sold_request_url)
            for_sale_homes_response = strip_json_beginning(for_sale_homes_response)
            sold_homes_response = strip_json_beginning(sold_homes_response)
            if for_sale_homes_response.get("errorMessage") == "Success" and sold_homes_response.get("errorMessage") == "Success":
                for_sale_homes = for_sale_homes_response.get("payload", {}).get("homes")
                sold_homes = sold_homes_response.get("payload", {}).get("homes")

                combined_homes = for_sale_homes + sold_homes
                return combined_homes

        # database miss so fall back to playwright fetch
        for_sale_homes_json, for_sale_request_url = fetch_homes_json_via_playwright(url)
        sold_homes_json, sold_request_url = fetch_homes_json_via_playwright(url + "/filter/include=sold-3mo")

        for_sale_homes = for_sale_homes_json.get("payload", {}).get("homes")
        sold_homes = sold_homes_json.get("payload", {}).get("homes")

        combined_homes = for_sale_homes + sold_homes
        with open('dumps/combined_homes.json', 'w', encoding='utf-8') as f:
            # dump `data` as JSON into the file, with nice indentation
            json.dump(combined_homes, f, ensure_ascii=False, indent=2)

        # persist for next time
        new_row = Zipcodes(
            zip_code=zipcode,
            sold_request_url=sold_request_url,
            for_sale_request_url=for_sale_request_url,
            last_updated=datetime.now()
        )
        session.add(new_row)
        session.commit()

        return combined_homes

    except SQLAlchemyError as db_err:
        session.rollback()
        # log the error, or re-raise if you want upstream handling
        print(f"[DB ERROR] could not update zip_to_bounds for {zipcode}: {db_err}")
        raise

    except Exception as e:
        session.rollback()
        # handle playwright or other failures if you like
        print(f"[ERROR] fetch_bounds_for_zip({zipcode}) failed: {e}")
        raise

    finally:
        session.close()


def fetch_homes_json_via_playwright(page_url):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent=get_ua()
        )
        page = context.new_page()

        # wait until network is quiet
        page.goto(page_url)
        time.sleep(1)

        # 2) Prepare to catch the GIS response
        #    The lambda will be evaluated on every response: we pick the one whose URL contains "/stingray/api/gis"
        with page.expect_response(lambda response: "/stingray/api/gis?" in response.url, timeout=10_000) as resp_info:
            # 3) Trigger the map‐refresh that fires that request
            page.click("[data-rf-test-id='map-zoom-control-minus'] button")
        gis_response = resp_info.value
        gis_request_url = gis_response.url

        raw_text = gis_response.text()
        if raw_text.startswith("{}&&"):
            raw_text = raw_text.split("&&", 1)[1]
        gis_payload = json.loads(raw_text)

        browser.close()
        return gis_payload, gis_request_url


def strip_json_beginning(raw_text: str):
    # raw_text is already the response body
    if raw_text.startswith("{}&&"):
        raw_text = raw_text.split("&&", 1)[1]
    return json.loads(raw_text)


# not currently used
def click_more_property_data_and_fetch_page_html(url: str, max_attempts: int = 3, headless: bool = True) -> str | None:
    """
    Navigate to `url`, attempt to click the "More Property History" button,
    and return the final page HTML, retrying up to `max_attempts` times on failure.
    """
    for attempt in range(1, max_attempts + 1):
        browser = None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
                    )
                )
                page = context.new_page()

                # 1) load the page
                page.goto(url, wait_until="domcontentloaded", timeout=15_000)

                # 2) give the JS a moment
                time.sleep(1)

                # 3) attempt to click the property-history button
                try:
                    btn = page.locator(
                        'div.sectionContainer[data-rf-test-id="propertyHistory"] '
                        'button.ExpandableLink.clickable',
                        has_text="See all property history"
                    )
                    btn.wait_for(state="visible", timeout=5_000)
                    btn.click(timeout=5_000)
                except TimeoutError:
                    print(f"[WARN] Attempt {attempt}: no history button, or timed out on {url}")
                except PlaywrightError as e:
                    print(f"[WARN] Attempt {attempt}: click failed on {url}: {e}")

                # 4) give the post-click UI a moment
                time.sleep(0.5)
                html = page.content()
                return html

        except Exception as e:
            print(f"[ERROR] Attempt {attempt}/{max_attempts} failed for {url}: {e}")
            if attempt < max_attempts:
                time.sleep(1)  # brief back-off before retrying
                continue
            else:
                print(f"[ERROR] All {max_attempts} attempts failed for {url}")
                return None

        finally:
            if browser:
                try:
                    browser.close()
                except Exception:
                    pass


# not currently used
def get_schools_via_html(soup):
    schools = []
    # find the outer school table container:
    schools_container = soup.find("div", class_="schools-content").find_all("div", class_="flex align-center")

    # loop over each school and grab important attributes
    for node in schools_container:
        # reset every iteration
        is_public = False
        is_elementary = False
        is_middle = False
        is_high = False
        distance_mi = None
        og_description = None

        # get the school rating
        rating_span = node.select_one("span.rating-num.font-size-base.font-weight-bold")
        if rating_span:
            rating = rating_span.get_text(strip=True)
        else:
            rating = None

        # get the school name
        name_span = node.select_one("div.ListItem__heading.font-body-base-bold.color-text-primary")
        if name_span:
            name = name_span.get_text(strip=True)
        else:
            name = None

        # get the school description
        description_span = node.select_one("p.ListItem__description.font-body-small-compact.color-text-secondary")
        if description_span:
            og_description = description_span.get_text(strip=True)
            is_public = og_description.startswith("Public")

            # level
            if "K-" in og_description:
                is_elementary = True
            if "-7" in og_description or "-8" in og_description:
                is_middle = True
            if "-12" in og_description:
                is_high = True

            # distance (grab the number before 'mi')
            m = re.search(r"([\d.]+)mi", og_description)
            distance_mi = float(m.group(1)) if m else None

        schools.append({
            "name": name,
            "is_elementary": is_elementary,
            "is_middle": is_middle,
            "is_high": is_high,
            "is_public": is_public,
            "rating": rating,
            "dist": distance_mi,
            "og_description": og_description
        })

    return schools


# not currently used
def get_price_history_via_html(soup):
    price_history = []

    # get price history information (along with details)
    price_history_timeline_contents = soup.select("div.PropertyHistoryEventRow")
    for history_row in price_history_timeline_contents:
        # date
        date = history_row.select_one("div.col-4 > p").get_text(strip=True)
        date = parser.parse(date)
        date = date.date().isoformat()

        # description
        description = history_row.select_one("div.description-col.col-4 > div").get_text(strip=True)

        # price
        price = history_row.select_one("div.price-col.number").get_text(strip=True)
        if price is not None:
            price = clean_price(price)

        price_history.append({
            "date": date,
            "description": description,
            "price": price
        })

    return price_history


# not currently used
def get_monthly_hoa_via_html(soup):
    node = soup.find(string="Association Fee: ")
    if node:
        cost = node.find_next("span").text.strip().replace("$", "")
        freq = soup.find(string="Association Fee Frequency: ")
        freq_text = freq.find_next("span").text if freq else ""
        monthly = float(cost) / 3 if freq_text == "Quarterly" else float(cost)
    else:
        monthly = None
    return monthly


# not currently used
def get_covered_spaces_via_html(soup):
    node = soup.find(string="Covered Spaces: ")
    span = node.find_next("span") if node else None
    return int(span.text) if span and span.text.isdigit() else None


# not currently used
def get_tax_annual_via_html(soup):
    tax_node = soup.find(string="Tax Annual Amount: ")
    span = tax_node.find_next("span") if tax_node else None
    tax_annual = span.text if span else None
    # remove leading '$' if present
    if tax_annual is not None:
        return clean_price(tax_annual)


# not currently used
def get_agents_info_via_html(soup):
    agent_container = soup.find_all("div", class_="agent-info-item flex flex-wrap")
    agent_name = ""
    agent_broker = ""
    for agent in agent_container:
        if agent_name != "" or agent_broker != "":
            agent_name += ", "
            agent_broker += ", "
        agent_name += agent.find("span", class_="agent-basic-details--heading").find("span").get_text(strip=True)
        full_broker_text = soup.select_one("span.agent-basic-details--broker > span").get_text(strip=True)
        agent_broker += full_broker_text.replace("•", "").strip()  # remove the dot and trim
    return ({'agent_name(s)': agent_name,
             'agent_broker(s)': agent_broker
             })


def get_list_date(home):
    raw = home.get('dom', {}).get('value')
    if raw is None:
        return None   # or some sensible default

    try:
        dom = int(raw)
    except (TypeError, ValueError):
        return None
    date = datetime.now(timezone.utc) - timedelta(days=dom)
    return date.isoformat()[:10]


def clean_price(input_str: str):
    # drop '(' and everything after
    s = input_str.split('(')[0]
    # remove any word starting with '\u' up to the next space
    s = re.sub(r'\\u[^ ]*', '', s)
    # strip leading dollar sign
    if s.startswith('$'):
        s = s[1:]
    # remove all commas
    s = s.replace(',', '')
    if s == "\u2014":
        s = ""
    # trim whitespace
    s = s.strip()

    try:
        # handle floats just in case
        return int(float(s))
    except ValueError:
        return None


def get_schools(data):
    schools = []
    schools_json = data.get("schoolsAndDistrictsInfo", {}).get("servingThisHomeSchools") or []
    for school in schools_json:
        is_public = False
        is_elementary = False
        is_middle = False
        is_high = False

        name = school.get("name")
        rating = school.get("greatSchoolsRating")
        distance_mi = school.get("distanceInMiles")

        institutionType = school.get("institutionType")
        if institutionType.startswith("Public"):
            is_public = True

        grade_range = school.get("gradeRanges")

        if "K-" in grade_range:
            is_elementary = True
        if "-7" in grade_range or "-8" in grade_range:
            is_middle = True
        if "-12" in grade_range:
            is_high = True

        schools.append({
            "name": name,
            "is_elementary": is_elementary,
            "is_middle": is_middle,
            "is_high": is_high,
            "is_public": is_public,
            "rating": rating,
            "dist": distance_mi,
        })

    return schools


def get_price_history(data):
    price_history = []

    # get price history information (along with details)
    price_history_events = data.get("propertyHistoryInfo", {}).get("events") or []
    for event in price_history_events:
        # date
        ts = event.get("eventDate", 0)
        dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        date = dt.date().isoformat()

        # description
        description = event.get("eventDescription")

        # price
        price = event.get("price")
        if price is not None:
            price = price

        price_history.append({
            "date": date,
            "description": description,
            "price": price
        })

    return price_history


def get_covered_spaces(data):
    # drill down to the list of super-groups
    super_groups = data.get("amenitiesInfo", {}).get("superGroups") or []

    covered_value = None
    for sg in super_groups:
        for group in sg.get("amenityGroups") or []:
            # look through each amenity entry
            for entry in group.get("amenityEntries") or []:
                if entry.get("amenityName") == "Covered Spaces":
                    # grab the first (and only) value
                    covered_value = entry.get("amenityValues")[0] or None
                    break
            if covered_value is not None:
                break
        if covered_value is not None:
            break
    if covered_value is not None:
        covered_value = float(covered_value)
    return covered_value


def get_tax_annual(data):
    # drill down to the list of super-groups
    super_groups = data.get("amenitiesInfo", {}).get("superGroups") or []

    tax_annual = None
    for sg in super_groups:
        for group in sg.get("amenityGroups") or []:
            # look through each amenity entry
            for entry in group.get("amenityEntries") or []:
                if entry.get("amenityName") == "Tax Annual Amount":
                    # grab the first (and only) value
                    tax_annual = entry.get("amenityValues")[0] or None
                    break
            if tax_annual is not None:
                break
        if tax_annual is not None:
            break
    if tax_annual is not None:
        tax_annual = clean_price(tax_annual)
    return tax_annual


def get_agents_info(data):
    agent_name = data.get("amenitiesInfo", {}).get("mlsDisclaimerInfo", {}).get("listingAgentName")
    agent_broker = data.get("amenitiesInfo", {}).get("mlsDisclaimerInfo", {}).get("listingBrokerName")
    return ({'agent_name': agent_name,
             'agent_broker': agent_broker
             })


def get_property_json(html):
    m = re.search(
        r'belowTheFold".*?"text"\s*:\s*"((?:\\.|[^"\\])*)"',  # search for the json dump
        html,
        flags=re.DOTALL
    )
    if not m:
        raise RuntimeError("Couldn't find the belowTheFold text block")

    raw = m.group(1)

    # un-escape JavaScript-style unicode (e.g. \u002F → /) and other escapes
    #    (this also turns \\n, \\" etc. into real newlines and quotes)
    decoded = bytes(raw, 'utf-8').decode('unicode_escape')

    # strip off the "{}&&" prefix that Redfin tacks on to avoid XSSI
    if decoded.startswith('{}&&'):
        decoded = decoded.split('&&', 1)[1]

    # parse into json
    return json.loads(decoded).get("payload")


def get_specific_info_on_each_property(homes_json):
    for home in homes_json:
        home['url'] = "https://www.redfin.com" + home.get('url')
        print(home['url'])
        try:
            # html = click_more_property_data_and_fetch_page_html(home['url'])
            html = fetch_html_via_https(home['url'])
            if not html:
                continue

            data = get_property_json(html)
            # with open('example_home_from_redfin.json', 'w', encoding='utf-8') as f:
            #     # dump `data` as JSON into the file, with nice indentation
            #     json.dump(data, f, ensure_ascii=False, indent=2)

            home['schools'] = get_schools(data)

            home['price_history'] = get_price_history(data)

            home['covered_spaces'] = get_covered_spaces(data)

            home['tax_annual_amount'] = get_tax_annual(data)

            agentsInfo = get_agents_info(data)
            home['agent_name'] = agentsInfo['agent_name']
            home['agent_broker'] = agentsInfo['agent_broker']

            home['list_date'] = get_list_date(home)

            home['zestimate'], home['zestimate_low'], home['zestimate_high'] = get_zestimate(home.get("streetLine", {}).get("value"), home.get("city"), home.get("state"), home.get("zip"))
        except Exception as e:
            print(f"[ERROR] processing {home['url']} raised {type(e).__name__}: {e}")
            continue

    return homes_json
