import random
import threading
from datetime import datetime, timedelta

# Group UA strings by browser family for weighted selection
USER_AGENTS = {
    'chrome': [
        # Windows Chrome
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/114.0.5735.199 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/115.0.5790.98 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/116.0.5845.187 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/117.0.5938.92 Safari/537.36",
        "Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/118.0.5993.90 Safari/537.36",
        # Mac Chrome
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/114.0.5735.199 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_2_3) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/115.0.5790.110 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_2_1) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/117.0.5938.92 Safari/537.36",
        # Linux Chrome
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/110.0.5481.77 Safari/537.36",
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/112.0.5615.49 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/109.0.5414.120 Safari/537.36",
    ],
    'safari': [
        # Desktop Safari (Mac)
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/16.1 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_6_8) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/15.6 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_6) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/16.4 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/14.1.2 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_3) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/16.5 Safari/605.1.15",
    ],
    'firefox': [
        # Windows Firefox
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:112.0) Gecko/20100101 "
        "Firefox/112.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) Gecko/20100101 "
        "Firefox/115.0",
        # Linux Firefox
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:112.0) Gecko/20100101 "
        "Firefox/112.0",
        "Mozilla/5.0 (X11; Fedora; Linux x86_64; rv:116.0) Gecko/20100101 "
        "Firefox/116.0",
        "Mozilla/5.0 (X11; Linux x86_64; rv:113.0) Gecko/20100101 Firefox/113.0",
        # Mac Firefox
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:114.0) Gecko/20100101 "
        "Firefox/114.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.14; rv:117.0) Gecko/20100101 "
        "Firefox/117.0",
    ],
    'edge': [
        # Desktop Edge (Windows)
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/114.0.5735.199 Safari/537.36 Edg/114.0.1823.67",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/115.0.5790.98 Safari/537.36 Edg/115.0.1901.203",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/116.0.5845.187 Safari/537.36 Edg/116.0.1938.69",
        # Mac Edge
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_3) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/117.0.5938.92 Safari/537.36 Edg/117.0.2045.43",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_1) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/118.0.5993.90 Safari/537.36 Edg/118.0.2088.50",
    ],
    'opera': [
        # Opera (Windows)
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36 OPR/99.0.0.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/115.0.5790.98 Safari/537.36 OPR/100.0.0.0",
        # Opera (Mac)
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_0) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/96.0.4664.120 Safari/537.36 OPR/96.0.4693.71",
        # Opera (Linux)
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/115.0.5790.110 Safari/537.36 OPR/101.0.4951.54",
    ],
}
# Approximate market share weights (sum to 1.0)
BROWSER_WEIGHTS = {
    'chrome': 0.65,
    'safari': 0.19,
    'firefox': 0.03,
    'edge': 0.03,
    'opera': 0.02,
    # others implicit
}

# Thread-safe state
_lock = threading.Lock()
# Next available time for each UA
_next_available: dict[str, datetime] = {}
# Last used UA to avoid immediate repeats
_last_used: str | None = None

# Base cooldown range
_MIN_COOLDOWN = timedelta(minutes=1)
_MAX_COOLDOWN = timedelta(minutes=15)
# Probability to bypass cooldown rules entirely
_BYPASS_PROB = 0.05

# Exponential backoff factor on repeated failures
_FAILURE_BACKOFF_FACTOR = 2.0
_failure_counts: dict[str, int] = {}


def get_ua() -> str:
    """
    Selects a user-agent with:
      - weighted browser distribution,
      - per-UA randomized cooldown,
      - occasional bypass,
      - no immediate repeats,
      - exponential backoff on failures.
    """
    global _last_used
    now = datetime.now()
    with _lock:
        # decide whether to bypass cooldown entirely
        if random.random() < _BYPASS_PROB:
            pool = [(b, ua) for b, ulist in USER_AGENTS.items() for ua in ulist]
        else:
            pool = []
            for browser, ulist in USER_AGENTS.items():
                for ua in ulist:
                    # check cooldown
                    next_time = _next_available.get(ua)
                    if not next_time or now >= next_time:
                        pool.append((browser, ua))
            # if nothing available, fallback to full
            if not pool:
                pool = [(b, ua) for b, ulist in USER_AGENTS.items() for ua in ulist]

        # remove last used UA to avoid repeat if possible
        filtered = [(b, ua) for b, ua in pool if ua != _last_used]
        if filtered:
            pool = filtered

        # apply browser weights
        browsers, uas = zip(*pool)
        weights = [BROWSER_WEIGHTS.get(b, 0.01) for b in browsers]
        # normalize weights
        total = sum(weights)
        norm_weights = [w/total for w in weights]

        # pick an agent
        ua = random.choices(uas, weights=norm_weights, k=1)[0]
        _last_used = ua

        # schedule next available time
        cooldown = random.uniform(
            _MIN_COOLDOWN.total_seconds(),
            _MAX_COOLDOWN.total_seconds()
        )
        # if this UA has failures, back off longer
        if ua in _failure_counts:
            cooldown *= (_FAILURE_BACKOFF_FACTOR ** _failure_counts[ua])
        _next_available[ua] = now + timedelta(seconds=cooldown)

        return ua


def release_ua(ua: str) -> None:
    """
    Clear cooldown and reset failure count for a UA (e.g. after a proxy error).
    """
    with _lock:
        _next_available.pop(ua, None)
        _failure_counts.pop(ua, None)


def report_failure(ua: str) -> None:
    """
    Increase failure count to trigger exponential backoff on that UA.
    """
    with _lock:
        _failure_counts[ua] = _failure_counts.get(ua, 0) + 1
