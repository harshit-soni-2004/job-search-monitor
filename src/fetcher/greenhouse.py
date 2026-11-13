"""Official Greenhouse public Board API fetcher."""

import html
import re
from typing import List, Optional
from urllib.parse import parse_qs, urlparse

from src.fetcher.base import BaseFetcher, FetchError
from src.models import JobListing, JobSource


class GreenhouseFetcher(BaseFetcher):
    """Fetches jobs using official public Greenhouse Boards API."""

    API_URL_TEMPLATE = "https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"

    @classmethod
    def extract_board_token(cls, url: str) -> Optional[str]:
        """Extract board token from various Greenhouse URL formats."""
        parsed = urlparse(url)
        path = parsed.path.strip("/")
        
        # Check query params (e.g. ?for=board_token)
        query = parse_qs(parsed.query)
        if "for" in query and query["for"]:
            return query["for"][0]

        # Check path: boards.greenhouse.io/{board_token} or job-boards.greenhouse.io/{board_token}
        parts = [p for p in path.split("/") if p]
        if parts:
            if parts[0] == "embed" and len(parts) > 2 and parts[1] == "job_board":
                pass
            elif parts[0] in ("v1", "boards") and len(parts) > 2:
                return parts[2]
            else:
                return parts[0]
        return None

    def fetch_jobs(self, source: JobSource) -> List[JobListing]:
        token = self.extract_board_token(source.careers_url)
        if not token:
            raise FetchError(f"Could not extract Greenhouse board token from {source.careers_url}")

        api_url = self.API_URL_TEMPLATE.format(board_token=token)
        self.logger.info(f"Querying official Greenhouse API for {source.company_name} ({token})...")

        self._sleep_rate_limit()
        try:
            resp = self.session.get(api_url, timeout=self.timeout)
            self._check_response_for_restrictions(resp, api_url)
            data = resp.json()
        except Exception as e:
            raise FetchError(f"Greenhouse API error for {token}: {e}") from e

        raw_jobs = data.get("jobs", [])
        listings: List[JobListing] = []

        for item in raw_jobs:
            job_id = item.get("id")
            title = (item.get("title") or "").strip()
            loc_data = item.get("location") or {}
            location = (loc_data.get("name") if isinstance(loc_data, dict) else str(loc_data)) or "Unspecified"
            job_url = item.get("absolute_url") or f"https://boards.greenhouse.io/{token}/jobs/{job_id}"
            
            # Format posted or updated date
            updated_at = item.get("updated_at")
            posted_date = updated_at[:10] if updated_at and len(updated_at) >= 10 else None

            # Unescape html content for description keywords matching
            raw_content = item.get("content") or ""
            description = html.unescape(re.sub(r"<[^>]+>", " ", raw_content)) if raw_content else None

            depts = item.get("departments") or []
            dept_name = ", ".join(d.get("name") for d in depts if isinstance(d, dict) and d.get("name"))

            listings.append(
                JobListing(
                    company=source.company_name,
                    title=title,
                    location=location.strip(),
                    url=job_url,
                    posted_date=posted_date,
                    description=description,
                    department=dept_name or None,
                )
            )

        self.logger.info(f"Greenhouse: retrieved {len(listings)} listings for {source.company_name}")
        return listings

