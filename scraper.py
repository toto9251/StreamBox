import re

import httpx
from selectolax.lexbor import LexborHTMLParser

from config import Config


class CatalogScraper:
    def __init__(self):
        self.client = httpx.Client(
            headers={"User-Agent": Config.USER_AGENT},
            follow_redirects=True,
            timeout=15.0,
        )
        self._active_domain = None

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def get_active_domain(self) -> str:
        """Finds the first working domain (cached after first call)."""
        if self._active_domain is not None:
            return self._active_domain

        for domain in Config.BASE_DOMAINS:
            try:
                r = self.client.get(domain, timeout=5.0)
                if r.status_code == 200:
                    self._active_domain = domain
                    return domain
            except httpx.RequestError:
                continue

        self._active_domain = Config.BASE_DOMAINS[0]
        return self._active_domain

    def get_series_title(self, url: str) -> str:
        """Extracts the actual series title from the series page."""
        try:
            response = self.client.get(url)
            response.raise_for_status()
            tree = LexborHTMLParser(response.text)

            selectors = [
                "h1.movie-title",
                "h1.series-title",
                "h1",
                ".series h1",
                "title",
            ]

            for selector in selectors:
                elements = tree.css(selector)
                if elements:
                    title = elements[0].text(strip=True)
                    if title:
                        title = re.sub(r'\s*[-|].*$', '', title)
                        return title

            return ""
        except httpx.HTTPError:
            return ""

    def parse_series(self, url: str) -> list:
        """Finds all seasons of a series - only unique season pages."""
        response = self.client.get(url)
        response.raise_for_status()

        tree = LexborHTMLParser(response.text)
        domain = self.get_active_domain()
        seasons = []
        seen_urls = set()

        for a in tree.css("a"):
            href = a.attributes.get("href", "")

            if not href or "/staffel-" not in href:
                continue

            # Only links ending at /staffel-X, not /staffel-X/episode-Y
            if "/episode-" in href:
                continue

            if href.startswith("/"):
                href = f"{domain}{href}"

            href = href.rstrip('/')

            if href in seen_urls:
                continue
            seen_urls.add(href)

            match = re.search(r'/staffel-(\d+)(?:/)?$', href)
            if match:
                season_num = int(match.group(1))
                seasons.append({
                    "number": season_num,
                    "url": href,
                })

        seasons.sort(key=lambda x: x["number"])
        return seasons

    def parse_season(self, url: str) -> list:
        """Finds all episodes of a season."""
        response = self.client.get(url)
        response.raise_for_status()

        tree = LexborHTMLParser(response.text)
        episodes = []
        domain = self.get_active_domain()

        for a in tree.css("a"):
            href = a.attributes.get("href", "")
            title = a.text(strip=True)
            if href and "/episode-" in href:
                if href.startswith("/"):
                    href = f"{domain}{href}"
                match = re.search(r'episode-(\d+)', href)
                episode_num = int(match.group(1)) if match else 0

                episodes.append({
                    "number": episode_num,
                    "title": title or f"Episode {episode_num}",
                    "url": href,
                })

        episodes.sort(key=lambda x: x["number"])
        return episodes

    def parse_episode(self, url: str) -> dict:
        """Fetches the host links from a single episode page."""
        response = self.client.get(url)
        response.raise_for_status()
        tree = LexborHTMLParser(response.text)

        hosts = []
        for btn in tree.css("button[data-play-url]"):
            play_url = btn.attributes.get("data-play-url", "")
            provider = btn.attributes.get("data-provider-name", "Unknown")
            language = btn.attributes.get("data-language-label", "Unknown")

            if play_url:
                if play_url.startswith("/"):
                    play_url = f"{self.get_active_domain()}{play_url}"

                hosts.append({
                    "redirect_url": play_url,
                    "provider": provider,
                    "language": language,
                })

        return {"url": url, "hosts": hosts}
