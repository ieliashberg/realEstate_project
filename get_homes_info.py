from playwright.sync_api import sync_playwright, TimeoutError, Error as PlaywrightError
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from dateutil import parser
import json
import time
import re


def get_homes_info(url: str):
    gis_url, headers, homes_payload = fetch_gis_url_headers_and_json(url)
    return get_specific_info_on_each_property(homes_payload)


def click_more_property_data_and_fetch_page_html(url: str, max_attempts: int = 3, headless: bool = True) -> str | None:
    """
    Navigate to `url`, attempt to click the "More Property History" button,
    and return the final page HTML, retrying up to `max_attempts` times on failure.
    """
    for attempt in range(1, max_attempts + 1):
        browser = None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=headless)
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/135.0.0.0 Safari/537.36"
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
                time.sleep(1)   # brief back-off before retrying
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


def fetch_gis_url_headers_and_json(page_url):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/135.0.0.0 Safari/537.36"
            )
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

        # 4) Pull out URL, request headers, and JSON body
        gis_url = gis_response.url
        gis_headers = gis_response.request.headers
        raw_text = gis_response.text()
        if raw_text.startswith("{}&&"):
            raw_text = raw_text.split("&&", 1)[1]
        gis_payload = json.loads(raw_text)

        browser.close()
        return gis_url, gis_headers, gis_payload


def get_schools(soup):
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


def get_price_history(soup):
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


def get_monthly_hoa(soup):
    node = soup.find(string="Association Fee: ")
    if node:
        cost = node.find_next("span").text.strip().replace("$", "")
        freq = soup.find(string="Association Fee Frequency: ")
        freq_text = freq.find_next("span").text if freq else ""
        monthly = float(cost) / 3 if freq_text == "Quarterly" else float(cost)
    else:
        monthly = None
    return monthly


def get_covered_spaces(soup):
    node = soup.find(string="Covered Spaces: ")
    span = node.find_next("span") if node else None
    return int(span.text) if span and span.text.isdigit() else None


def get_tax_annual(soup):
    tax_node = soup.find(string="Tax Annual Amount: ")
    span = tax_node.find_next("span") if tax_node else None
    tax_annual = span.text if span else None
    # remove leading '$' if present
    if tax_annual is not None:
        return clean_price(tax_annual)


def get_agents_info(soup):
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
    dom = int(home.get('dom', {}).get('value'))
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


def get_specific_info_on_each_property(homes_json):
    homes = homes_json["payload"]["homes"]
    for home in homes:
        home['url'] = "https://www.redfin.com" + home.get('url')
        print(home['url'])
        try:
            html = click_more_property_data_and_fetch_page_html(home['url'])
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")

            home['schools'] = get_schools(soup)

            home['price_history'] = get_price_history(soup)

            home['covered_spaces'] = get_covered_spaces(soup)

            home['tax_annual_amount'] = get_tax_annual(soup)

            agentsInfo = get_agents_info(soup)
            home['agent_name(s)'] = agentsInfo['agent_name(s)']
            home['agent_broker(s)'] = agentsInfo['agent_broker(s)']

            home['list_date'] = get_list_date(home)

        except Exception as e:
            print(f"[ERROR] processing {home['url']} raised {type(e).__name__}: {e}")
            continue

    return homes
