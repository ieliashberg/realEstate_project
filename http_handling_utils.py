from user_agents import get_ua
from curl_cffi import requests
import json
import logging

# configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

redfin_base_headers = {
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

zillow_base_headers = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "en-US,en;q=0.9",
    "cache-control": "max-age=0",
    "If-None-Match": 'W/"1d59b-SyW5u0OLYrC/Mo43YjlbdDUS+Ss"',
    "priority": "u=0, i",
    "sec-ch-ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "macOS",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "cookie": 'zguid=24|%24509d6256-a790-463a-b0e4-f162fa8aaeda; _ga=GA1.2.689147679.1745276489; zg_anonymous_id=%225fd0ed85-ee44-4777-b7df-730273167f9f%22; _gcl_au=1.1.1200349471.1745276490; _scid=2wuV62kx6f6gp82PpiH_Qa6QUWgizttgYRkMgQ; _fbp=fb.1.1745276490391.6947470937842691; _pin_unauth=dWlkPU1qSXpOVGc0WW1NdE9HTmhZUzAwTlRjd0xXSTNNemt0TUROaVpqRTJNamhpTkdVNA; _tt_enable_cookie=1; _ttp=01JSD9BMQWXB8S05QKAZS54BPE_.tt.1; _lr_env_src_ats=false; _pxvid=0ad6dcbc-248a-11f0-8069-6dcab37cb77c; g_state={"i_l":0}; loginmemento=1|4dab51ea01f4285d74b994acd98e2784af6d3297e7d4b2496c9cefd9caba51f0; userid=X|3|60ec9f2f44cdb0e4%7C7%7C4CxjdfFT-BIWH49UlQwKkZS55HESdbdTaJGwpO3vNmw%3D; zjs_user_id=%22X1-ZUrqucbkxso9ah_22g4q%22; __ssid=e888c97a8843c910129191fe1a3693f; zgcus_lbut=; zgcus_aeut=223461151; zgcus_lddid=4438f328d5ff985ce848b769feaf29f8; zgcus_ludi=0e34bcde-2658-11f0-84e1-16299cc6089b-22346; optimizelyEndUserId=oeu1746170629291r0.23458933500415746; __spdt=e9d7c9f75a014d058c82b9337b4ca062; optimizelySession=0; _gcl_gs=2.1.k1$i1746945381$u59079846; _gac_UA-21174015-56=1.1746945461.Cj0KCQjw8vvABhCcARIsAOCfwwr0GNh1v_3oLFkPp2qes-LhkH0rSUo8-F415Rs4DKix0PFObQaXO0AaAn6-EALw_wcB; _gcl_aw=GCL.1746945462.Cj0KCQjw8vvABhCcARIsAOCfwwr0GNh1v_3oLFkPp2qes-LhkH0rSUo8-F415Rs4DKix0PFObQaXO0AaAn6-EALw_wcB; OptanonConsent=isGpcEnabled=0&datestamp=Sun+May+11+2025+00%3A11%3A03+GMT-0700+(Pacific+Daylight+Time)&version=202301.2.0&isIABGlobal=false&hosts=&consentId=3ac7a60d-7d42-4624-93a3-57c7491ec68f&interactionCount=1&landingPath=https%3A%2F%2Fwww.zillow.com%2Frental-manager%2Fproperties%3FpostingPath%3Dtrue%26address%3D1169-Sesame-Dr-Sunnyvale-CA-94087%26subNavFilterType%3Dall&groups=1%3A1%2C2%3A1%2C3%3A1%2C4%3A1; FSsampler=1223018350; _ScCbts=%5B%22565%3Bchrome.2%3A2%3A5%22%2C%22570%3Bchrome.2%3A2%3A5%22%5D; _sctr=1%7C1748329200000; _lr_sampling_rate=100; zgsession=1|792580f5-e81b-4179-8bf8-4b14f1c17f51; ZILLOW_SID=1|AAAAAVVbFRIBVVsVEsbojgOe9YjHGK56hdJiuGQVWfGExRHY%2BOGHnOvmHfN%2BPa5pznRwB3ha%2FDTYajggHarkjBJx%2BfiO%2BLfyVA; _gid=GA1.2.1009941801.1748649106; _lr_retry_request=true; zjs_user_id_type=%22encoded_zuid%22; pxcts=0b9c6d94-3db1-11f0-81a2-3fa9ddc004a3; AWSALB=B1dMdKl0kYsHS3gJCzhB+vVs7OCdLD7OHY2jaa7f0jOvLknJqc2a4Q6fSHNslZzG/ZRo1tme7S4FvxXPgQPQH6wrUdN4gGJo7dOQFuh5igaWKxqBk9bSnB81II/v; AWSALBCORS=B1dMdKl0kYsHS3gJCzhB+vVs7OCdLD7OHY2jaa7f0jOvLknJqc2a4Q6fSHNslZzG/ZRo1tme7S4FvxXPgQPQH6wrUdN4gGJo7dOQFuh5igaWKxqBk9bSnB81II/v; JSESSIONID=3BB2C5BA698B711E7AF090AB0A5180A5; connectId=%7B%22puid%22%3A%22d1db9786a6a7b3d320cc23b1b583d2452bc7d4abd1584122f4cd1e20ca278d97%22%2C%22vmuid%22%3A%22I3krTKpjCZGTanLXR8ZCjoI84fRJY3iSdd5z2KAwGzdM-SbVo5Oic_-PDq35HpEWPbawuew6n38xY_tpfixAgA%22%2C%22connectid%22%3A%22I3krTKpjCZGTanLXR8ZCjoI84fRJY3iSdd5z2KAwGzdM-SbVo5Oic_-PDq35HpEWPbawuew6n38xY_tpfixAgA%22%2C%22connectId%22%3A%22I3krTKpjCZGTanLXR8ZCjoI84fRJY3iSdd5z2KAwGzdM-SbVo5Oic_-PDq35HpEWPbawuew6n38xY_tpfixAgA%22%2C%22ttl%22%3A86400000%2C%22lastSynced%22%3A1748649106476%2C%22lastUsed%22%3A1748649106476%7D; search=6|1751241107185%7Crect%3D33.99854626111227%2C-111.60184712304687%2C33.21164022967015%2C-112.64829487695312%26rid%3D40326%26disp%3Dmap%26mdm%3Dauto%26p%3D1%26listPriceActive%3D1%26fs%3D1%26fr%3D0%26mmm%3D0%26rs%3D0%26singlestory%3D0%26housing-connector%3D0%26parking-spots%3Dnull-%26abo%3D0%26garage%3D0%26pool%3D0%26ac%3D0%26waterfront%3D0%26finished%3D0%26unfinished%3D0%26cityview%3D0%26mountainview%3D0%26parkview%3D0%26waterview%3D0%26hoadata%3D1%26zillow-owned%3D0%263dhome%3D0%26showcase%3D0%26featuredMultiFamilyBuilding%3D0%26onlyRentalStudentHousingType%3D0%26onlyRentalIncomeRestrictedHousingType%3D0%26onlyRentalMilitaryHousingType%3D0%26onlyRentalDisabledHousingType%3D0%26onlyRentalSeniorHousingType%3D0%26commuteMode%3Ddriving%26commuteTimeOfDay%3Dnow%09%0940326%09%7B%22isList%22%3Atrue%2C%22isMap%22%3Atrue%7D%09%09%09%09%09; DoubleClickSession=true; __gads=ID=b5f537f5f6bc637c:T=1745276489:RT=1748649108:S=ALNI_MZysw2XcRae3yohTPC0e90AKiafXg; __gpi=UID=0000101070d03c53:T=1745276489:RT=1748649108:S=ALNI_MaxAwWMUhgci1pcCUTWe7-auH1M6g; __eoi=ID=4256e09445cf4f2f:T=1745276489:RT=1748649108:S=AA-AfjZWkAMdCEtYuRgcA6TwhbhC; _csrf=WSltonBzlfjcNUsTLeTQLiQq; _clck=3fctni%7C2%7Cfwd%7C0%7C1937; _rdt_uuid=1745276490218.8eecb8f9-2dc7-4031-a14a-609dca782e52; _scid_r=1QuV62kx6f6gp82PpiH_Qa6QUWgizttgYRkMmg; zjs_anonymous_id=%22SDK-1ed120cc-741f-4989-b6ac-3af7ded47ab2%22; ttcsid=1748651576160::-6yAotpfVHGt3RJC9U4W.22.1748651576161; _uetsid=0c7609c03db111f08e27edb5a8b0774b; _uetvid=6d2e0de006e011f09d079130a08835b3; fs_lua=1.1748651576154; fs_uid=#o-21MVN0-na1#6e732f35-5e10-4253-baa9-2dde3d9f2c86:25f2940e-2c03-4542-839d-350363e2a76d:1748649141094::2#/1777618158; tfpsi=3ad3f6a4-6473-4c83-93eb-056d40830f50; ttcsid_CN5P33RC77UF9CBTPH9G=1748651576160::D01T4OlaE2Yetf5FQmFi.22.1748651576390; _clsk=e1hfxm%7C1748651576663%7C4%7C0%7Cl.clarity.ms%2Fcollect; _px3=64d67e71bcb7ce84d444b9273fc505302c8cba273d63f489026c432fa8cce385:yoIiaSsEQoWIQTCebyXP49hdeDwOlXeaK8gBYUrOMrAbbdc+o/0diBvTSUupcNlu6fmSlUwnBPMmpWrv05Jqcw==:1000:jiR48S8D1nUIGFI2wbdAlubBppT3yQFqmBtU0TfjNkSpNpfdWY40+z+uVh0bAv0DxfwZLpOMhL9RRfMHgqVK9OuRwk9FW+LkKf8nU7ZgyTcViv5zO3AomXK9r2mTnEQnxculyPVI3K3vxBox0/wNDlRKhhdoIjythTV/oR8LYqS8NLFrbF+BgJZlyX3CGRZzDFveMTcLxKdDcO7kuludtNYU++iPqyLbqeBwgsq5+f8=; _dd_s=rum=0&expire=1748652727708; rjs-trace=a3ecb25cf5281770e3d5f8dc7a:45150423727f82a11948ae4e07:',
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
}


def fetch_html_via_https(url: str, base_heads, proxy: dict[str, str] | None = None):
    header_with_ua = put_ua_in_header(base_heads)
    resp = requests.get(
        url=url,
        headers=header_with_ua,
        proxies=proxy,
        impersonate="chrome124"  # curl_cffi convenience for User-Agent spoofing
    )
    resp.raise_for_status()
    return resp.text


def put_ua_in_header(base_heads) -> dict[str, str]:
    ua = get_ua()
    return {
        **base_heads,
        "User-Agent": ua,
    }


def strip_json_beginning(raw_text: str):
    # raw_text is already the response body
    if raw_text.startswith("{}&&"):
        raw_text = raw_text.split("&&", 1)[1]
    return json.loads(raw_text)
