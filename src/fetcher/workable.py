"""Official Workable public Widget API fetcher."""

from typing import List, Optional
from urllib.parse import urlparse

from src.fetcher.base import BaseFetcher, FetchError
from src.models import JobListing, JobSource


class WorkableFetcher(BaseFetcher):
    """Fetches jobs using official public Workable API."""

    API_URL_TEMPLATE = "https://apply.workable.com/api/v1/widget/accounts/{company}"

    @classmethod
    def extract_company(cls, url: str) -> Optional[str]:
        """Extract company from apply.workable.com/{company}."""
        parsed = urlparse(url)
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if parts:
            return parts[0]
        return None

    def fetch_jobs(self, source: JobSource) -> List[JobListing]:
        company = self.extract_company(source.careers_url)
        if not company:
            raise FetchError(f"Could not extract Workable company slug from {source.careers_url}")

        api_url = self.API_URL_TEMPLATE.format(company=company)
        self.logger.info(f"Querying official Workable API for {source.company_name} ({company})...")

        self._sleep_rate_limit()
        try:
            resp = self.session.get(api_url, timeout=self.timeout)
            self._check_response_for_restrictions(resp, api_url)
            data = resp.json()
        except Exception as e:
            raise FetchError(f"Workable API error for {company}: {e}") from e

        raw_jobs = data.get("jobs", [])
        listings: List[JobListing] = []

        for item in raw_jobs:
            title = (item.get("title") or "").strip()
            shortcode = item.get("shortcode")
            job_url = item.get("url") or f"https://apply.workable.com/{company}/j/{shortcode}/"
            
            loc = item.get("location") or {}
            loc_parts = []
            if isinstance(loc, dict):
                for k in ["city", "region", "country"]:
                    if loc.get(k):
                        loc_parts.append(str(loc[k]))
                if item.get("telecommuting"):
                    loc_parts.append("Remote")
            location = ", ".join(loc_parts) if loc_parts else "Unspecified"

            published = item.get("published")
            posted_date = published[:10] if published and len(published) >= 10 else None

            dept = item.get("department")

            listings.append(
                JobListing(
                    company=source.company_name,
                    title=title,
                    location=location,
                    url=job_url,
                    posted_date=posted_date,
                    description=None,
                    department=dept,
                )
            )

        self.logger.info(f"Workable: retrieved {len(listings)} listings for {source.company_name}")
        return listings

