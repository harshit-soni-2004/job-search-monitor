"""Official Workday public Job Board API fetcher."""

import re
from typing import List, Optional, Tuple
from urllib.parse import urlparse

from src.fetcher.base import BaseFetcher, FetchError
from src.models import JobListing, JobSource


class WorkdayFetcher(BaseFetcher):
    """Fetches jobs using official public Workday CXS JSON API."""

    @classmethod
    def extract_workday_parts(cls, url: str) -> Optional[Tuple[str, str, str]]:
        """
        Extract (domain, tenant, site) from Workday URLs.
        Example: https://postman.wd108.myworkdayjobs.com/careers
                 domain = postman.wd108.myworkdayjobs.com
                 tenant = postman
                 site = careers
        """
        parsed = urlparse(url)
        domain = parsed.netloc
        if "myworkdayjobs.com" not in domain:
            return None

        tenant = domain.split(".")[0]
        path_parts = [p for p in parsed.path.strip("/").split("/") if p and p != "job"]
        site = path_parts[0] if path_parts else "jobs"

        return domain, tenant, site

    def fetch_jobs(self, source: JobSource) -> List[JobListing]:
        parts = self.extract_workday_parts(source.careers_url)
        if not parts:
            raise FetchError(f"Could not parse Workday URL structure from {source.careers_url}")

        domain, tenant, site = parts
        api_url = f"https://{domain}/wday/cxs/{tenant}/{site}/jobs"
        self.logger.info(f"Querying official Workday CXS API for {source.company_name} ({tenant}/{site})...")

        self._sleep_rate_limit()
        payload = {"appliedFacets": {}, "limit": 50, "offset": 0, "searchText": ""}
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            resp = self.session.post(api_url, json=payload, headers=headers, timeout=self.timeout)
            self._check_response_for_restrictions(resp, api_url)
            data = resp.json()
        except Exception as e:
            raise FetchError(f"Workday API error for {source.company_name}: {e}") from e

        job_postings = data.get("jobPostings", [])
        listings: List[JobListing] = []

        for item in job_postings:
            title = (item.get("title") or "").strip()
            loc_text = item.get("locationsText") or "Unspecified"
            external_path = item.get("externalPath") or ""
            job_url = f"https://{domain}/{site}{external_path}" if external_path else source.careers_url

            posted_on = item.get("postedOn")
            posted_date = None
            if posted_on:
                m = re.search(r"(\d{4}-\d{2}-\d{2})", str(posted_on))
                if m:
                    posted_date = m.group(1)

            listings.append(
                JobListing(
                    company=source.company_name,
                    title=title,
                    location=loc_text.strip(),
                    url=job_url,
                    posted_date=posted_date,
                    priority=source.priority,
                )
            )

        self.logger.info(f"Workday: retrieved {len(listings)} listings for {source.company_name}")
        return listings

