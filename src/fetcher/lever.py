"""Official Lever public Postings API fetcher."""

from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urlparse

from src.fetcher.base import BaseFetcher, FetchError
from src.models import JobListing, JobSource


class LeverFetcher(BaseFetcher):
    """Fetches jobs using official public Lever Postings API."""

    API_URL_TEMPLATE = "https://api.lever.co/v0/postings/{company}?mode=json"

    @classmethod
    def extract_company(cls, url: str) -> Optional[str]:
        """Extract company slug from jobs.lever.co/{company}."""
        parsed = urlparse(url)
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if parts:
            return parts[0]
        return None

    def fetch_jobs(self, source: JobSource) -> List[JobListing]:
        company = self.extract_company(source.careers_url)
        if not company:
            raise FetchError(f"Could not extract Lever company slug from {source.careers_url}")

        api_url = self.API_URL_TEMPLATE.format(company=company)
        self.logger.info(f"Querying official Lever API for {source.company_name} ({company})...")

        self._sleep_rate_limit()
        try:
            resp = self.session.get(api_url, timeout=self.timeout)
            self._check_response_for_restrictions(resp, api_url)
            data = resp.json()
        except Exception as e:
            raise FetchError(f"Lever API error for {company}: {e}") from e

        if not isinstance(data, list):
            raise FetchError(f"Unexpected response structure from Lever API: {data}")

        listings: List[JobListing] = []
        for item in data:
            title = (item.get("text") or "").strip()
            job_url = item.get("hostedUrl") or ""
            cats = item.get("categories") or {}
            location = cats.get("location") or cats.get("allLocations") or "Unspecified"
            if isinstance(location, list):
                location = ", ".join(location)

            team = cats.get("team") or ""
            desc = item.get("descriptionPlain") or ""

            # Convert epoch milliseconds createdAt to YYYY-MM-DD
            created_at = item.get("createdAt")
            posted_date = None
            if created_at and isinstance(created_at, (int, float)):
                try:
                    posted_date = datetime.fromtimestamp(created_at / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")
                except Exception:
                    posted_date = None

            listings.append(
                JobListing(
                    company=source.company_name,
                    title=title,
                    location=str(location).strip(),
                    url=job_url,
                    posted_date=posted_date,
                    description=desc,
                    department=team or None,
                )
            )

        self.logger.info(f"Lever: retrieved {len(listings)} listings for {source.company_name}")
        return listings

