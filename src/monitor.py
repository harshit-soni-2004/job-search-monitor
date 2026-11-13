"""Core monitor orchestrating fetching, matching, Excel updating, and reporting."""

from datetime import datetime
import os
from pathlib import Path
from typing import List, Optional

from src.config import AppConfig
from src.excel_handler import ExcelHandler
from src.fetcher.base import AccessRestrictedError, FetchError
from src.fetcher.registry import FetcherRegistry
from src.logger import setup_logger
from src.matcher import JobMatcher
from src.models import (
    DailyRunSummary,
    EvaluationOutcome,
    ExcludedListing,
    MatchResult,
    SourceRunResult,
)
from src.notifier import trigger_windows_notification


class JobMonitor:
    """Orchestrates the entire job search monitoring process."""

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or AppConfig.from_file()
        self.logger = setup_logger(log_dir=self.config.log_dir, log_level=self.config.log_level)
        self.excel_handler = ExcelHandler(self.config.workbook_path)
        self.matcher = JobMatcher()

    def run(self) -> DailyRunSummary:
        """Execute a full monitoring run across all active sources."""
        started_at = datetime.now()
        self.logger.info("=" * 60)
        self.logger.info(f"Starting Job Search Monitor at {started_at.strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"Target Workbook: {self.config.workbook_path}")
        self.logger.info("=" * 60)

        # 1. Read sources from Excel
        try:
            sources = self.excel_handler.load_sources()
        except Exception as e:
            self.logger.error(f"Failed to load sources from Excel workbook: {e}")
            raise

        active_sources = [s for s in sources if s.active]
        priority_a_sources = [s for s in active_sources if "Priority A" in s.priority]
        priority_b_sources = [s for s in active_sources if "Priority B" in s.priority]
        self.logger.info(
            f"Found {len(sources)} total sources ({len(active_sources)} active: "
            f"{len(priority_a_sources)} Priority A, {len(priority_b_sources)} Priority B)."
        )

        all_matches: List[MatchResult] = []
        confirmed_matches: List[MatchResult] = []
        review_needed_matches: List[MatchResult] = []
        excluded_2plus_list: List[ExcludedListing] = []
        source_results: List[SourceRunResult] = []
        total_scanned = 0

        # 2. Iterate each source
        for source in active_sources:
            self.logger.info("-" * 50)
            self.logger.info(f"[{source.priority}] Processing: {source.company_name} [{source.careers_url}]")
            
            fetcher = FetcherRegistry.get_fetcher_for_url(
                url=source.careers_url,
                user_agent=self.config.user_agent,
                timeout=self.config.request_timeout,
                delay=self.config.rate_limit_delay,
                logger=self.logger,
            )

            listings = []
            fetch_success = False
            error_reason = None

            try:
                listings = fetcher.fetch_jobs(source)
                fetch_success = True
            except AccessRestrictedError as e:
                error_reason = f"Access restricted / anti-bot: {e}"
                self.logger.warning(f"Restricted access for {source.company_name}: {e}")
            except (FetchError, Exception) as e:
                error_reason = str(e)
                self.logger.warning(f"Standard fetch failed for {source.company_name}: {e}")

            # Optional TinyFish fallback if standard fetch failed
            if not fetch_success and os.getenv("TINYFISH_API_KEY"):
                self.logger.info(f"Attempting optional TinyFish fallback for {source.company_name}...")
                try:
                    tf_fetcher = FetcherRegistry.get_fetcher_for_url(
                        url=source.careers_url,
                        user_agent=self.config.user_agent,
                        timeout=self.config.request_timeout,
                        delay=self.config.rate_limit_delay,
                        logger=self.logger,
                        use_tinyfish_fallback=True,
                    )
                    listings = tf_fetcher.fetch_jobs(source)
                    fetch_success = True
                    error_reason = None
                except Exception as tf_err:
                    self.logger.info(f"TinyFish fallback also could not read {source.company_name}: {tf_err}")
                    error_reason = f"Standard fetch failed & TinyFish unparseable: {tf_err}"

            if fetch_success:
                total_scanned += len(listings)
                matched_for_source = 0

                for listing in listings:
                    outcome: EvaluationOutcome = self.matcher.evaluate_listing(listing, source)
                    if outcome.status == "CONFIRMED" and outcome.match_result:
                        all_matches.append(outcome.match_result)
                        confirmed_matches.append(outcome.match_result)
                        matched_for_source += 1
                    elif outcome.status == "NEEDS_REVIEW" and outcome.match_result:
                        all_matches.append(outcome.match_result)
                        review_needed_matches.append(outcome.match_result)
                        matched_for_source += 1
                    elif outcome.status == "EXCLUDED_2PLUS" and outcome.excluded_listing:
                        excluded_2plus_list.append(outcome.excluded_listing)

                status_str = "SUCCESS" if listings else "EMPTY"
                source_results.append(
                    SourceRunResult(
                        company_name=source.company_name,
                        careers_url=source.careers_url,
                        priority=source.priority,
                        status=status_str,
                        total_found=len(listings),
                        matched_count=matched_for_source,
                    )
                )
                self.logger.info(
                    f"Result for {source.company_name}: {len(listings)} listings found, "
                    f"{matched_for_source} matching candidates."
                )
            else:
                self.logger.warning(f"Marking {source.company_name} as NEEDS REVIEW ({error_reason})")
                source_results.append(
                    SourceRunResult(
                        company_name=source.company_name,
                        careers_url=source.careers_url,
                        priority=source.priority,
                        status="NEEDS_REVIEW",
                        error_message=error_reason or "Page unparseable via public API / HTML",
                    )
                )

        # 3. Update Excel Matches Sheet safely
        self.logger.info("=" * 60)
        self.logger.info(
            f"Updating Matches sheet with {len(all_matches)} listings "
            f"({len(confirmed_matches)} confirmed, {len(review_needed_matches)} review needed)..."
        )
        new_added, existing_updated = self.excel_handler.update_matches(all_matches)
        
        # Record 2+ year excluded listings separately in Excluded sheet
        if excluded_2plus_list:
            self.logger.info(f"Recording {len(excluded_2plus_list)} excluded listings in 'Excluded' sheet...")
            self.excel_handler.update_excluded(excluded_2plus_list)

        finished_at = datetime.now()
        successful_cnt = sum(1 for r in source_results if r.status in ("SUCCESS", "EMPTY"))
        needs_review_cnt = sum(1 for r in source_results if r.status == "NEEDS_REVIEW")
        failed_cnt = sum(1 for r in source_results if r.status in ("FAILED", "RESTRICTED"))

        summary = DailyRunSummary(
            started_at=started_at,
            finished_at=finished_at,
            total_sources=len(sources),
            active_sources=len(active_sources),
            successful_sources=successful_cnt,
            failed_sources=failed_cnt,
            needs_review_sources=needs_review_cnt,
            total_listings_scanned=total_scanned,
            new_matches_added=new_added,
            existing_matches_updated=existing_updated,
            source_results=source_results,
            confirmed_matches=confirmed_matches,
            review_needed_matches=review_needed_matches,
            excluded_listings_2plus=excluded_2plus_list,
        )

        # 4. Generate and display daily summary
        self._report_summary(summary)

        # 5. Local Windows notification (only when new matches or sources need review)
        if summary.new_matches_added > 0 or summary.needs_review_sources > 0:
            parts = []
            if len(summary.confirmed_matches) > 0:
                parts.append(f"{len(summary.confirmed_matches)} confirmed")
            if len(summary.review_needed_matches) > 0:
                parts.append(f"{len(summary.review_needed_matches)} need review")
            msg = f"{', '.join(parts) or 'Check finished'}. Scanned {summary.total_listings_scanned} listings ({summary.active_sources} sources)."
            trigger_windows_notification(
                title="Job Search Monitor",
                message=msg,
                logger=self.logger,
            )

        return summary

    def _report_summary(self, summary: DailyRunSummary):
        """Format and output the detailed run summary with confirmed matches, reviews, and exclusions."""
        duration = (summary.finished_at - summary.started_at).total_seconds()
        
        lines = [
            "",
            "============================== DAILY JOB SEARCH SUMMARY ==============================",
            f"Date / Time:       {summary.started_at.strftime('%Y-%m-%d %H:%M:%S')} (Duration: {duration:.1f}s)",
            f"Workbook:          {self.config.workbook_path}",
            f"Sources Checked:   {summary.active_sources} active ({summary.successful_sources} succeeded, {summary.needs_review_sources} need review)",
            f"Listings Scanned:  {summary.total_listings_scanned}",
            f"Confirmed Matches: {len(summary.confirmed_matches)} (Stated 0-1 yr / Freshers / Graduates)",
            f"Review Needed:     {len(summary.review_needed_matches)} (Experience missing / only on employer portal)",
            f"2+ Yr Exclusions:  {len(summary.excluded_listings_2plus)} listings excluded (kept out of Matches sheet)",
            "--------------------------------------------------------------------------------------",
        ]

        # Section 1: Confirmed Matches
        lines.append("\n[1] CONFIRMED MATCHES (Stated min exp 0-1 years or explicitly accepts freshers/graduates):")
        if summary.confirmed_matches:
            for idx, m in enumerate(summary.confirmed_matches, 1):
                j = m.job
                lines.append(f"  {idx}. {j.company} - {j.title}")
                lines.append(f"     Location:        {j.location}")
                lines.append(f"     Direct Job Link: {j.url}")
                lines.append(f"     Exact Exp Text:  \"{m.experience_text}\"")
                lines.append(f"     Matched Details: {m.matched_criteria}")
                lines.append("")
        else:
            lines.append("  (No listings with confirmed 0-1 year stated experience found in this run.)\n")

        # Section 2: Listings Needing Experience Review
        lines.append("[2] LISTINGS NEEDING EXPERIENCE REVIEW (Role & location match, but experience is unverified or only on application page):")
        if summary.review_needed_matches:
            for idx, m in enumerate(summary.review_needed_matches, 1):
                j = m.job
                lines.append(f"  {idx}. {j.company} - {j.title}")
                lines.append(f"     Location:        {j.location}")
                lines.append(f"     Direct Job Link: {j.url}")
                lines.append(f"     Review Note:     {m.experience_text}")
                lines.append(f"     Matched Details: {m.matched_criteria}")
                lines.append("")
        else:
            lines.append("  (None)\n")

        # Section 3: Exclusions Due to 2+ Years
        lines.append(f"[3] EXCLUSIONS DUE TO 2+ YEARS ({len(summary.excluded_listings_2plus)} listings excluded from Matches sheet):")
        if summary.excluded_listings_2plus:
            for idx, ex in enumerate(summary.excluded_listings_2plus, 1):
                lines.append(f"  {idx}. {ex.company} - {ex.title} ({ex.location})")
                lines.append(f"     Direct Job Link: {ex.url}")
                lines.append(f"     Exclusion Reason: {ex.reason}")
                lines.append("")
        else:
            lines.append("  (None)\n")

        # Section 4: Sources that could not be checked
        lines.append("[4] SOURCES THAT COULD NOT BE CHECKED (Marked 'Needs Review' due to anti-bot / restrictions):")
        uncheckable = [r for r in summary.source_results if r.status in ("NEEDS_REVIEW", "FAILED", "RESTRICTED")]
        if uncheckable:
            for idx, r in enumerate(uncheckable, 1):
                lines.append(f"  {idx}. {r.company_name:<22} | URL: {r.careers_url}")
                lines.append(f"     Reason: {r.error_message}")
        else:
            lines.append("  (All sources checked successfully.)")

        # Section 5: Strict Compliance Confirmation
        lines.append("\n--------------------------------------------------------------------------------------")
        confirmed_with_2plus = [
            m for m in summary.confirmed_matches
            if self.matcher.EXCLUDE_2PLUS_REGEX.search(m.job.title or "")
            or self.matcher.EXCLUDE_2PLUS_REGEX.search(m.job.description or "")
            or self.matcher.MID_SENIOR_LEVEL_REGEX.search(m.job.title or "")
        ]
        if not confirmed_with_2plus:
            lines.append("CONFIRMATION: VERIFIED. Zero (0) roles requiring 2+ years were included as confirmed matches.")
        else:
            lines.append(f"WARNING: Detected {len(confirmed_with_2plus)} roles with potential 2+ year requirements in confirmed list!")
        lines.append("======================================================================================\n")

        summary_text = "\n".join(lines)
        print(summary_text)

        if self.config.save_daily_summary_log:
            os.makedirs(self.config.log_dir, exist_ok=True)
            summary_path = Path(self.config.log_dir) / "daily_summaries.log"
            try:
                with open(summary_path, "a", encoding="utf-8") as f:
                    f.write(summary_text + "\n")
            except Exception as e:
                self.logger.warning(f"Could not append to daily_summaries.log: {e}")
