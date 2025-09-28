from bs4 import BeautifulSoup
from utils.http_utils import fetch_html_via_https, ZILLOW_HEADERS as zillow_base_headers
import re
import json
from html import unescape


def get_working_uas():
    scraped_uas = scrape_uas()
    working_uas = []
    for ua in scraped_uas:
        try:
            html = fetch_html_via_https(url="https://www.zillow.com/rental-manager/price-my-rental/results/1169-sesame-dr-sunnyvale-ca-94087/", base_heads=zillow_base_headers)
            print(html[:1000])
            working_uas.append(ua)
        except Exception as e:
            print("Error getting html: {}".format(e))
            continue
    print("Working UAs: {}".format(working_uas))
    return working_uas
def scrape_uas():
    try:
        html = fetch_html_via_https(url="https://www.useragents.me/")
    except Exception as e:
        print("Error getting html: {}".format(e))
        return None
    
    soup = BeautifulSoup(html, "html.parser")

    ta = soup.select_one('#most-common-desktop-useragents-json-csv textarea')
    if not ta:
        raise RuntimeError("Could not find the textarea in the target div.")

    raw = unescape(ta.get_text(strip=True))

    m = re.search(r'\[[\s\S]*\]', raw)
    json_text = m.group(0) if m else raw

    data = json.loads(json_text)
    formatted_data = format_user_agents(data)

    return formatted_data

def format_user_agents(data, mac_only=False):
    #sort by pct desc (if present), else keep order
    try:
        rows = sorted(data, key=lambda r: r.get("pct", 0), reverse=True)
    except Exception:
        rows = list(data)

    # extract UA strings
    uas = [r["ua"] for r in rows if isinstance(r, dict) and "ua" in r]

    # optional filter to macOS only
    if mac_only:
        uas = [u for u in uas if "Macintosh" in u]

    # de-dupe but preserve order
    seen = set()
    deduped = []
    for u in uas:
        if u not in seen:
            seen.add(u)
            deduped.append(u)

    return deduped
