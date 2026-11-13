"""Official SmartRecruiters public Postings API fetcher."""

import html
import re
from typing import List, Optional
from urllib.parse import urlparse

from src.fetcher.base import BaseFetcher, FetchError
from src.models import JobListing, JobSource


class SmartRecruitersFetcher(BaseFetcher):
    """Fetches jobs using official public SmartRecruiters API."""

    API_URL_TEMPLATE = "https://api.smartrecruiters.com/v1/companies/{company}/postings"

    @classmethod
    def extract_company(cls, url: str) -> Optional[str]:
        """Extract company identifier from careers.smartrecruiters.com/{company}."""
        parsed = urlparse(url)
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if parts:
            return parts[0]
        return None

    def fetch_jobs(self, source: JobSource) -> List[JobListing]:
        company = self.extract_company(source.careers_url)
        if not company:
            raise FetchError(f"Could not extract SmartRecruiters company slug from {source.careers_url}")

        api_url = self.API_URL_TEMPLATE.format(company=company)
        self.logger.info(f"Querying official SmartRecruiters API for {source.company_name} ({company})...")

        self._sleep_rate_limit()
        try:
            resp = self.session.get(api_url, timeout=self.timeout)
            self._check_response_for_restrictions(resp, api_url)
            data = resp.json()
        except Exception as e:
            raise FetchError(f"SmartRecruiters API error for {company}: {e}") from e

        raw_jobs = data.get("content", [])
        listings: List[JobListing] = []

        for item in raw_jobs:
            job_id = item.get("id")
            title = (item.get("name") or "").strip()
            job_url = f"https://jobs.smartrecruiters.com/{company}/{job_id}"
            
            loc = item.get("location") or {}
            loc_parts = []
            if isinstance(loc, dict):
                if loc.get("city"):
                    loc_parts.append(loc["city"])
                if loc.get("region"):
                    loc_parts.append(loc["region"])
                if loc.get("country"):
                    loc_parts.append(loc["country"].upper())
                if loc.get("remote"):
                    loc_parts.append("Remote")
            location = ", ".join(loc_parts) if loc_parts else "Unspecified"

            released_date = item.get("releasedDate")
            posted_date = released_date[:10] if released_date and len(released_date) >= 10 else None
            
            dept = item.get("department", {}).get("label") if isinstance(item.get("department"), dict) else None

            # Fetch qualifications & description for candidate India roles
            desc = None
            is_india = (
                (isinstance(loc, dict) and loc.get("country", "").lower() == "in")
                or any(city in location.lower() for city in ["india", "bengaluru", "bangalore", "hyderabad", "mumbai", "pune", "gurgaon", "gurugram", "noida", "chennai"])
            )
            is_relevant_role = any(kw in title.lower() for kw in ["software", "sde", "engineer", "developer", "sre", "devops", "platform", "backend"])

            if is_india and is_relevant_role and job_id:
                try:
                    detail_resp = self.session.get(
                        f"https://api.smartrecruiters.com/v1/companies/{company}/postings/{job_id}",
                        timeout=(3, 5),
                    )
                    if detail_resp.status_code == 200:
                        d_json = detail_resp.json()
                        sections = d_json.get("jobAd", {}).get("sections", {})
                        parts = []
                        if sections.get("jobDescription", {}).get("text"):
                            parts.append(sections["jobDescription"]["text"])
                        if sections.get("qualifications", {}).get("text"):
                            parts.append(sections["qualifications"]["text"])
                        if parts:
                            raw_desc = "\n\n".join(parts)
                            desc = html.unescape(re.sub(r"<[^>]+>", " ", raw_desc)).strip()
                except Exception:
                    pass

            listings.append(
                JobListing(
                    company=source.company_name,
                    title=title,
                    location=location,
                    url=job_url,
                    posted_date=posted_date,
                    description=desc,
                    department=dept,
                )
            )

        self.logger.info(f"SmartRecruiters: retrieved {len(listings)} listings for {source.company_name}")
        return listings

