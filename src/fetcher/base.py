"""Base Fetcher class with safe, polite HTTP client."""

import logging
import time
from typing import List, Optional
import requests

from src.models import JobListing, JobSource


class FetchError(Exception):
    """General fetching failure."""
    pass


class AccessRestrictedError(FetchError):
    """Raised when access is gated by login, CAPTCHA, or anti-bot protections."""
    pass


class BaseFetcher:
    """Abstract base class for all job board and career page fetchers."""

    def __init__(self, user_agent: str, timeout: int = 10, delay: float = 1.0, logger: Optional[logging.Logger] = None):
        # Use a tuple for strict (connect, read) timeouts to prevent socket hangs
        self.timeout = (5, timeout if isinstance(timeout, int) else 10)
        self.delay = delay
        self.logger = logger or logging.getLogger("JobSearchMonitor")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })

    def _sleep_rate_limit(self):
        if self.delay > 0:
            time.sleep(self.delay)

    def _check_response_for_restrictions(self, response: requests.Response, url: str):
        """Detect access restrictions, Cloudflare / anti-bot challenge pages or logins."""
        status = response.status_code
        content_lower = response.text.lower() if response.text else ""

        # Check for forbidden, unauthorized, or rate-limited responses
        if status in (401, 403, 429):
            msg = f"HTTP {status} access restricted or rate limited on {url}."
            self.logger.warning(f"[POLITE NOTICE] {msg} Gracefully skipping without bypass.")
            raise AccessRestrictedError(msg)

        # Check for common bot challenge signatures
        challenge_markers = [
            "cf-chl-bypass",
            "cloudflare turnstile",
            "challenge-running",
            "please verify you are a human",
            "recaptcha",
            "hcaptcha",
            "bot detection",
            "ddos protection by cloudflare",
        ]
        if any(marker in content_lower for marker in challenge_markers):
            msg = f"Anti-bot or CAPTCHA challenge detected on {url}."
            self.logger.warning(f"[POLITE NOTICE] {msg} Gracefully skipping as per public policy.")
            raise AccessRestrictedError(msg)

        response.raise_for_status()

    def fetch_jobs(self, source: JobSource) -> List[JobListing]:
        """Fetch job listings for the given source."""
        raise NotImplementedError

