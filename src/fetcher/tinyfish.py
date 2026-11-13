"""Optional TinyFish Web Fetch / Search fallback for public career portals."""

import os
import re
from typing import List, Optional
from bs4 import BeautifulSoup
import requests

from src.fetcher.base import AccessRestrictedError, BaseFetcher, FetchError
from src.fetcher.generic import GenericFetcher
from src.models import JobListing, JobSource


class TinyFishFetcher(BaseFetcher):
    """
    Optional fallback fetcher using TinyFish Web Fetch/Search.
    Strictly uses free public fetch/search only - never paid Agent or Browser endpoints.
    """

    TINYFISH_FETCH_URL = "https://api.tinyfish.ai/v1/fetch"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_key = os.getenv("TINYFISH_API_KEY", "").strip()

    def fetch_jobs(self, source: JobSource) -> List[JobListing]:
        url = source.careers_url

        if not self.api_key:
            self.logger.info(
                f"[TinyFish] TINYFISH_API_KEY not set. Cannot use TinyFish fallback for {source.company_name}."
            )
            raise FetchError(
                f"Needs Review: Standard fetcher unparseable and TINYFISH_API_KEY not configured for {url}"
            )

        self.logger.info(f"[TinyFish] Attempting public fetch via TinyFish for {source.company_name}...")
        self._sleep_rate_limit()

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": self.session.headers.get("User-Agent", "JobSearchMonitor/1.0"),
        }
        payload = {
            "url": url,
            "mode": "fetch",  # Public fetch only - never browser/agent
        }

        try:
            resp = requests.post(self.TINYFISH_FETCH_URL, json=payload, headers=headers, timeout=self.timeout)
            
            if resp.status_code in (401, 403):
                msg = f"Needs Review: TinyFish unauthorized or invalid key (HTTP {resp.status_code})"
                self.logger.warning(f"[TinyFish] {msg}")
                raise FetchError(msg)
            
            if resp.status_code in (402, 429):
                msg = f"Needs Review: TinyFish free limit / quota exceeded (HTTP {resp.status_code})"
                self.logger.warning(f"[TinyFish] {msg}")
                raise FetchError(msg)

            self._check_response_for_restrictions(resp, url)
            data = resp.json()
            html_text = data.get("html") or data.get("content") or ""

        except (AccessRestrictedError, FetchError):
            raise
        except Exception as e:
            raise FetchError(f"Needs Review: TinyFish request failed for {source.company_name}: {e}") from e

        if not html_text:
            raise FetchError(f"Needs Review: TinyFish returned empty content for {url}")

        # Parse fetched HTML with standard generic parser
        soup = BeautifulSoup(html_text, "html.parser")
        generic = GenericFetcher(
            user_agent=self.session.headers.get("User-Agent", ""),
            timeout=self.timeout,
            delay=self.delay,
            logger=self.logger,
        )
        
        json_ld_jobs = generic._extract_json_ld(soup, source, url)
        if json_ld_jobs:
            return json_ld_jobs
        
        return generic._extract_html_links(soup, source, url)

