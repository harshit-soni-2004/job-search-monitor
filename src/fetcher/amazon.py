"""Official Amazon public Careers search API fetcher."""

import html
import re
from typing import List
from src.fetcher.base import BaseFetcher, FetchError
from src.models import JobListing, JobSource


class AmazonFetcher(BaseFetcher):
    """Fetches jobs from Amazon's official public jobs search API."""

    API_URL = "https://www.amazon.jobs/en/search.json?country=IND&result_limit=100"

    def fetch_jobs(self, source: JobSource) -> List[JobListing]:
        self.logger.info(f"Querying official Amazon Jobs API for {source.company_name} in India...")
        self._sleep_rate_limit()

        try:
            resp = self.session.get(self.API_URL, timeout=self.timeout)
            self._check_response_for_restrictions(resp, self.API_URL)
            data = resp.json()
        except Exception as e:
            raise FetchError(f"Amazon Jobs API error: {e}") from e

        raw_jobs = data.get("jobs", [])
        listings: List[JobListing] = []

        for item in raw_jobs:
            title = (item.get("title") or "").strip()
            city = item.get("city") or "India"
            job_path = item.get("job_path") or ""
            job_url = f"https://www.amazon.jobs{job_path}" if job_path else "https://www.amazon.jobs/en/"
            
            posted_date = item.get("posted_date")
            raw_desc = f"{item.get('description') or ''}\n\nBasic Qualifications:\n{item.get('basic_qualifications') or ''}\n\nPreferred Qualifications:\n{item.get('preferred_qualifications') or ''}"
            clean_desc = html.unescape(re.sub(r"<[^>]+>", " ", raw_desc)).strip()

            listings.append(
                JobListing(
                    company=source.company_name,
                    title=title,
                    location=city,
                    url=job_url,
                    posted_date=posted_date,
                    description=clean_desc if clean_desc else None,
                    department=item.get("business_category"),
                    priority=source.priority,
                )
            )

        self.logger.info(f"Amazon: retrieved {len(listings)} India listings")
        return listings

