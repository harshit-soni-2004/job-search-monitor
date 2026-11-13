"""Generic public webpage fetcher with Schema.org JSON-LD support."""

import json
import re
from typing import List, Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

from src.fetcher.base import BaseFetcher, FetchError
from src.models import JobListing, JobSource


class GenericFetcher(BaseFetcher):
    """Fetches jobs from public web pages using Schema.org JSON-LD or semantic HTML."""

    def fetch_jobs(self, source: JobSource) -> List[JobListing]:
        url = source.careers_url
        self.logger.info(f"Checking public career page for {source.company_name} at {url}...")

        self._sleep_rate_limit()
        try:
            resp = self.session.get(url, timeout=self.timeout)
            self._check_response_for_restrictions(resp, url)
            html_text = resp.text
        except Exception as e:
            raise FetchError(f"Failed to fetch public career page {url}: {e}") from e

        soup = BeautifulSoup(html_text, "html.parser")

        # 1. Try finding official Schema.org JSON-LD JobPosting data
        json_ld_jobs = self._extract_json_ld(soup, source, url)
        if json_ld_jobs:
            self.logger.info(f"Extracted {len(json_ld_jobs)} listings via Schema.org JSON-LD for {source.company_name}")
            return json_ld_jobs

        # 2. Try extracting semantic HTML job links
        html_jobs = self._extract_html_links(soup, source, url)
        self.logger.info(f"Extracted {len(html_jobs)} listings via HTML links for {source.company_name}")
        return html_jobs

    def _extract_json_ld(self, soup: BeautifulSoup, source: JobSource, page_url: str) -> List[JobListing]:
        """Extract JobPosting structured data from <script type='application/ld+json'> tags."""
        listings: List[JobListing] = []
        scripts = soup.find_all("script", type=lambda t: t and "application/ld+json" in t.lower())

        for script in scripts:
            try:
                content = script.string
                if not content:
                    continue
                data = json.loads(content)
            except Exception:
                continue

            # Data could be a single object, list of objects, or @graph
            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                if "@graph" in data and isinstance(data["@graph"], list):
                    items = data["@graph"]
                else:
                    items = [data]

            for item in items:
                if not isinstance(item, dict):
                    continue
                item_type = item.get("@type")
                if item_type != "JobPosting" and not (isinstance(item_type, list) and "JobPosting" in item_type):
                    continue

                title = item.get("title") or item.get("name") or ""
                if not title:
                    continue

                job_url = item.get("url")
                if job_url:
                    job_url = urljoin(page_url, job_url)
                else:
                    job_url = page_url

                # Location parsing
                location = "Unspecified"
                job_loc = item.get("jobLocation")
                if isinstance(job_loc, dict):
                    address = job_loc.get("address")
                    if isinstance(address, dict):
                        addr_parts = [
                            address.get("addressLocality"),
                            address.get("addressRegion"),
                            address.get("addressCountry"),
                        ]
                        location = ", ".join(p for p in addr_parts if p)
                    elif isinstance(address, str):
                        location = address
                elif isinstance(job_loc, list) and job_loc:
                    location = "Multiple Locations"

                # Remote / telecommute flag
                job_location_type = item.get("jobLocationType")
                if job_location_type and "TELECOMMUTE" in str(job_location_type).upper():
                    location = f"{location} (Remote)".strip()

                date_posted = item.get("datePosted")
                posted_date = date_posted[:10] if date_posted and len(date_posted) >= 10 else None

                raw_desc = item.get("description")
                desc_text = None
                if raw_desc:
                    desc_text = re.sub(r"<[^>]+>", " ", raw_desc).strip()

                listings.append(
                    JobListing(
                        company=source.company_name,
                        title=str(title).strip(),
                        location=location.strip(),
                        url=job_url,
                        posted_date=posted_date,
                        description=desc_text,
                    )
                )

        return listings

    def _extract_html_links(self, soup: BeautifulSoup, source: JobSource, page_url: str) -> List[JobListing]:
        """Fallback heuristics: extract links pointing to job details."""
        listings: List[JobListing] = []
        seen_urls = set()

        job_url_keywords = ["/job/", "/jobs/", "/careers/", "/position/", "/positions/", "/openings/", "/opening/"]
        
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue

            full_url = urljoin(page_url, href)
            if full_url in seen_urls:
                continue

            path_lower = urlparse(full_url).path.lower()
            text = a.get_text(separator=" ", strip=True)

            # Heuristic: URL contains a job-path indicator or link text looks like a job title
            is_job_path = any(kw in path_lower for kw in job_url_keywords)
            if not is_job_path:
                continue

            # Skip common utility links
            if text.lower() in ("careers", "view all", "all jobs", "search", "back", "apply", "learn more", "read more"):
                continue

            # Must have reasonable title length
            if 3 < len(text) < 120 and not text.lower().startswith("http"):
                seen_urls.add(full_url)
                listings.append(
                    JobListing(
                        company=source.company_name,
                        title=text,
                        location="Unspecified",
                        url=full_url,
                    )
                )

        return listings

