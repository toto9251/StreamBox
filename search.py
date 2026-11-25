"""Series search on SerienStream with cache for fast lookups."""

import json
import re
from datetime import datetime, timedelta

import httpx
from selectolax.lexbor import LexborHTMLParser

from config import Config
from settings import CONFIG_DIR


SEARCH_PATHS = [
    "/serien",
    "/search",
    "/api/search",
]

# Cache valid for 7 days
CACHE_DURATION_DAYS = 7
CACHE_FILE = CONFIG_DIR / "series_cache.json"


def _is_cache_valid():
    """Checks if the cache is still valid."""
    if not CACHE_FILE.exists():
        return False

    try:
        stat = CACHE_FILE.stat()
        modified = datetime.fromtimestamp(stat.st_mtime)
        age = datetime.now() - modified
        return age < timedelta(days=CACHE_DURATION_DAYS)
    except OSError:
        return False


def _load_cache():
    """Loads the cache from file."""
    if not _is_cache_valid():
        return None

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        date_str = datetime.fromtimestamp(CACHE_FILE.stat().st_mtime).strftime('%Y-%m-%d')
        print(f"[✓] Cache loaded: {len(data)} series (as of {date_str})")
        return data
    except (json.JSONDecodeError, OSError) as e:
        print(f"[!] Cache error: {e}")
        return None


def _save_cache(series_list):
    """Saves the series list to cache."""
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(series_list, f, ensure_ascii=False, indent=2)
        print(f"[✓] Cache saved: {len(series_list)} series")
    except OSError as e:
        print(f"[!] Failed to save cache: {e}")


def _clean_title(text: str) -> str:
    """Cleans the title."""
    text = (text or "").strip()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\s*[-|].*$', '', text)
    return text.strip()


def _extract_series_links(html: str, base_domain: str) -> list:
    """Extracts series links from HTML."""
    out = []
    tree = LexborHTMLParser(html)

    selectors = [
        "a[href*='/serie/']",
        "a[href*='/series/']",
        ".seriesList a",
        ".search-results a",
        "div.series a",
        "ul.series a",
    ]

    found_links = set()

    for selector in selectors:
        for a in tree.css(selector):
            href = a.attributes.get("href", "")
            raw_title = a.text()
            title = _clean_title(raw_title)

            if not href or "/staffel-" in href or "/episode-" in href:
                continue
            if not title or len(title) < 2:
                continue

            if href.startswith("/"):
                href = f"{base_domain}{href}"

            href = re.sub(r'/staffel-\d+.*$', '', href)
            href = re.sub(r'/episode-\d+.*$', '', href)

            if href not in found_links:
                found_links.add(href)
                out.append({"title": title, "url": href})

    return out


def _extract_from_json(payload, base_domain: str) -> list:
    """Extracts series from JSON responses."""
    out = []

    items = []
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        for key in ("data", "results", "series", "items", "hydra:member"):
            if isinstance(payload.get(key), list):
                items = payload[key]
                break

    for it in items:
        if not isinstance(it, dict):
            continue

        title = _clean_title(
            str(it.get("title") or it.get("name") or it.get("series") or "")
        )
        url = str(it.get("url") or it.get("link") or it.get("href") or "")
        slug = str(it.get("slug") or "")

        if not title or len(title) < 2:
            continue
        if not url and slug:
            url = f"{base_domain}/serie/{slug}"
        if url.startswith("/"):
            url = f"{base_domain}{url}"
        if not url:
            continue

        url = re.sub(r'/staffel-\d+.*$', '', url)
        url = re.sub(r'/episode-\d+.*$', '', url)

        out.append({"title": title, "url": url})

    return out


def _fetch_all_series(debug: bool = False) -> list:
    """Fetches all series from SerienStream (for cache building)."""
    all_series = []
    seen_urls = set()
    seen_titles = set()

    if debug:
        print("[DEBUG] Loading all series...")

    with httpx.Client(
        headers={
            "User-Agent": Config.USER_AGENT,
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        },
        follow_redirects=True,
        timeout=30.0,
    ) as client:
        for domain in Config.BASE_DOMAINS:
            for path in SEARCH_PATHS:
                url = f"{domain}{path}"

                if debug:
                    print(f"[DEBUG] Trying: {url}")

                try:
                    r = client.get(url)
                except httpx.RequestError as e:
                    if debug:
                        print(f"[DEBUG] Error: {e}")
                    continue

                if r.status_code != 200:
                    if debug:
                        print(f"[DEBUG] Status: {r.status_code}")
                    continue

                ctype = (r.headers.get("content-type") or "").lower()

                if debug:
                    print(f"[DEBUG] Content-Type: {ctype}, Length: {len(r.text)}")

                if "json" in ctype:
                    try:
                        batch = _extract_from_json(r.json(), domain)
                        if debug:
                            print(f"[DEBUG] JSON hits: {len(batch)}")
                    except (json.JSONDecodeError, ValueError) as e:
                        if debug:
                            print(f"[DEBUG] JSON error: {e}")
                        batch = []
                else:
                    batch = _extract_series_links(r.text, domain)
                    if debug:
                        print(f"[DEBUG] HTML hits: {len(batch)}")

                for item in batch:
                    key_url = item["url"].lower().rstrip('/')
                    key_title = item["title"].lower().strip()

                    if key_url in seen_urls or key_title in seen_titles:
                        continue

                    seen_urls.add(key_url)
                    seen_titles.add(key_title)
                    all_series.append(item)

                if len(all_series) > 5000:
                    break

            if len(all_series) > 5000:
                break

    if debug:
        print(f"[DEBUG] Total: {len(all_series)} series")

    return all_series


def search_series(query: str, debug: bool = False, force_refresh: bool = False) -> list:
    """Searches for a series with cache support."""
    query = query.strip()
    if not query:
        return []

    query_lower = query.lower()

    cached_series = None
    if not force_refresh:
        cached_series = _load_cache()

    if cached_series is None:
        print("[*] Loading series list (first run or cache expired)...")
        print("[!] This may take 30-60 seconds...")
        all_series = _fetch_all_series(debug)

        if all_series:
            _save_cache(all_series)
            cached_series = all_series
        else:
            print("[!] No series loaded.")
            return []

    filtered = [
        series for series in cached_series
        if query_lower in series["title"].lower()
    ]

    if debug:
        print(f"[DEBUG] Filtered: {len(filtered)} hits for '{query}'")

    return filtered


def fuzzy_match(query: str, results: list) -> list:
    """Sorts results by relevance to the search query."""
    q = query.lower()
    exact, starts, contains = [], [], []

    for r in results:
        t = r["title"].lower()
        if t == q:
            exact.append(r)
        elif t.startswith(q):
            starts.append(r)
        else:
            contains.append(r)

    return exact + starts + contains


def refresh_cache(debug: bool = False):
    """Manually refreshes the cache."""
    print("[*] Refreshing series cache...")
    all_series = _fetch_all_series(debug)

    if all_series:
        _save_cache(all_series)
        print(f"[✓] Cache refreshed: {len(all_series)} series")
        return True
    else:
        print("[!] Cache refresh failed")
        return False
