"""Official Ashby public Job Board API fetcher."""

from typing import List, Optional
from urllib.parse import urlparse

from src.fetcher.base import BaseFetcher, FetchError
from src.models import JobListing, JobSource


class AshbyFetcher(BaseFetcher):
    """Fetches jobs using official public Ashby Job Board API."""

    API_URL_TEMPLATE = "https://api.ashbyhq.com/posting-api/job-board/{board_name}"

    @classmethod
    def extract_board_name(cls, url: str) -> Optional[str]:
        """Extract board name from jobs.ashbyhq.com/{board_name}."""
        parsed = urlparse(url)
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if parts:
            return parts[0]
        return None

    def fetch_jobs(self, source: JobSource) -> List[JobListing]:
        board = self.extract_board_name(source.careers_url)
        if not board:
            raise FetchError(f"Could not extract Ashby board name from {source.careers_url}")

        api_url = self.API_URL_TEMPLATE.format(board_name=board)
        self.logger.info(f"Querying official Ashby API for {source.company_name} ({board})...")

        self._sleep_rate_limit()
        try:
            resp = self.session.get(api_url, timeout=self.timeout)
            self._check_response_for_restrictions(resp, api_url)
            data = resp.json()
        except Exception as e:
            raise FetchError(f"Ashby API error for {board}: {e}") from e

        raw_jobs = data.get("jobs", [])
        listings: List[JobListing] = []

        for item in raw_jobs:
            title = (item.get("title") or "").strip()
            job_url = item.get("jobUrl") or f"https://jobs.ashbyhq.com/{board}/{item.get('id')}"
            location = item.get("location") or "Unspecified"
            
            published_at = item.get("publishedAt")
            posted_date = published_at[:10] if published_at and len(published_at) >= 10 else None
            
            dept = item.get("department")

            listings.append(
                JobListing(
                    company=source.company_name,
                    title=title,
                    location=str(location).strip(),
                    url=job_url,
                    posted_date=posted_date,
                    description=None,
                    department=dept,
                )
            )

        self.logger.info(f"Ashby: retrieved {len(listings)} listings for {source.company_name}")
        return listings

