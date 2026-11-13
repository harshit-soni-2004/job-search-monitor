"""Comprehensive test suite for Job Search Monitor."""

import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
import openpyxl

from src.excel_handler import ExcelHandler
from src.fetcher.base import AccessRestrictedError, BaseFetcher
from src.fetcher.greenhouse import GreenhouseFetcher
from src.fetcher.lever import LeverFetcher
from src.fetcher.ashby import AshbyFetcher
from src.fetcher.workday import WorkdayFetcher
from src.fetcher.amazon import AmazonFetcher
from src.fetcher.registry import FetcherRegistry
from src.matcher import JobMatcher
from src.models import JobListing, JobSource, MatchResult


class TestJobMatcher(unittest.TestCase):
    def setUp(self):
        self.matcher = JobMatcher()

    def test_positive_sde_match_and_ranking(self):
        source = JobSource(
            company_name="Razorpay",
            careers_url="https://job-boards.greenhouse.io/razorpaysoftwareprivatelimited",
            priority="Priority A",
            location_preferences=["Bengaluru", "Remote"],
        )
        job = JobListing(
            company="Razorpay",
            title="Software Engineer I - Backend",
            location="Bengaluru, Karnataka",
            url="https://job-boards.greenhouse.io/razorpay/jobs/101",
            description="Requires 1+ years of experience developing Java, Spring Boot microservices with Redis, MySQL and Docker.",
            priority="Priority A",
        )
        result = self.matcher.evaluate(job, source)
        self.assertIsNotNone(result)
        self.assertEqual(result.role_family, "SDE / Backend")
        self.assertEqual(result.match_status, "Confirmed")
        self.assertGreater(result.score, 10.0)
        self.assertIn("Java", result.matched_criteria)
        self.assertIn("Spring Boot", result.matched_criteria)

    def test_positive_sre_match(self):
        source = JobSource(
            company_name="Swiggy",
            careers_url="https://careers.smartrecruiters.com/Swiggy",
            priority="Priority A",
            location_preferences=["Bengaluru", "Remote"],
        )
        job = JobListing(
            company="Swiggy",
            title="Associate Site Reliability Engineer",
            location="Bengaluru",
            url="https://careers.smartrecruiters.com/Swiggy/201",
            description="0-1 years of experience managing Kubernetes, Terraform, AWS infrastructure and Prometheus observability.",
            priority="Priority A",
        )
        result = self.matcher.evaluate(job, source)
        self.assertIsNotNone(result)
        self.assertEqual(result.role_family, "SRE / DevOps")
        self.assertEqual(result.match_status, "Confirmed")
        self.assertIn("Kubernetes", result.matched_criteria)
        self.assertIn("Prometheus", result.matched_criteria)

    def test_strict_2plus_years_exclusion(self):
        source = JobSource(company_name="TestCorp", careers_url="https://example.com")
        for bad_phrase in ["2+ years", "2-4 years", "minimum 2 years", "at least 2 years", "3+ years"]:
            job = JobListing(
                company="TestCorp",
                title="Software Engineer I",
                location="Bengaluru",
                url=f"https://example.com/jobs/{bad_phrase.replace(' ', '_')}",
                description=f"Requires {bad_phrase} of experience in backend development.",
            )
            outcome = self.matcher.evaluate_listing(job, source)
            self.assertEqual(outcome.status, "EXCLUDED_2PLUS")
            self.assertIsNone(self.matcher.evaluate(job, source))

    def test_missing_experience_needs_review(self):
        source = JobSource(company_name="TestCorp", careers_url="https://example.com")
        job = JobListing(
            company="TestCorp",
            title="Software Engineer I",
            location="Bengaluru",
            url="https://example.com/jobs/no_exp",
            description="Bachelor degree in CS or equivalent. Familiar with Java.",
        )
        outcome = self.matcher.evaluate_listing(job, source)
        self.assertEqual(outcome.status, "NEEDS_REVIEW")
        result = self.matcher.evaluate(job, source)
        self.assertIsNotNone(result)
        self.assertEqual(result.match_status, "Needs experience review")

    def test_internship_exclusion(self):
        source = JobSource(company_name="TestCorp", careers_url="https://example.com")
        job = JobListing(
            company="TestCorp",
            title="Software Engineer Intern",
            location="Bengaluru",
            url="https://example.com/jobs/intern",
        )
        self.assertIsNone(self.matcher.evaluate(job, source))

    def test_senior_exclusion(self):
        source = JobSource(company_name="TestCorp", careers_url="https://example.com")
        job = JobListing(
            company="TestCorp",
            title="Senior Staff Backend Engineer",
            location="Bengaluru",
            url="https://example.com/jobs/senior",
        )
        self.assertIsNone(self.matcher.evaluate(job, source))

        # Also test numbered level exclusions (SDE II, Software Engineer 2)
        job_sde2 = JobListing(
            company="TestCorp",
            title="Software Development Engineer II",
            location="Bengaluru",
            url="https://example.com/jobs/sde2",
        )
        self.assertIsNone(self.matcher.evaluate(job_sde2, source))

    def test_excessive_experience_exclusion(self):
        source = JobSource(company_name="TestCorp", careers_url="https://example.com")
        job = JobListing(
            company="TestCorp",
            title="Software Engineer - 5+ years experience",
            location="Bengaluru",
            url="https://example.com/jobs/exp5",
        )
        self.assertIsNone(self.matcher.evaluate(job, source))

    def test_foreign_remote_rejection(self):
        source = JobSource(company_name="TestCorp", careers_url="https://example.com")
        job = JobListing(
            company="TestCorp",
            title="Software Engineer I",
            location="Remote - US Only (United States)",
            url="https://example.com/jobs/us-remote",
        )
        self.assertIsNone(self.matcher.evaluate(job, source))


class TestExcelHandler(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.wb_path = Path(self.temp_dir.name) / "test_jobs.xlsx"
        self.handler = ExcelHandler(self.wb_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_populate_watchlist_and_load(self):
        self.handler.populate_watchlist()
        self.assertTrue(self.wb_path.exists())

        sources = self.handler.load_sources()
        # Should have all 69 companies loaded (21 Priority A + 48 Priority B)
        self.assertGreaterEqual(len(sources), 60)
        # Priority A must be ordered first
        self.assertEqual(sources[0].priority, "Priority A")

    def test_notes_and_status_preservation_and_demo_removal(self):
        """CRITICAL: Ensure user notes, status changes, and custom columns are NEVER overwritten."""
        self.handler.create_template_workbook()

        source = JobSource(company_name="Razorpay", careers_url="https://example.com", priority="Priority A")
        job_real = JobListing(
            company="Razorpay",
            title="Software Engineer I",
            location="Bengaluru",
            url="https://job-boards.greenhouse.io/razorpay/jobs/real-101",
            posted_date="2026-11-01",
            priority="Priority A",
        )
        match_real = MatchResult(
            job=job_real,
            matched_criteria="[SDE / Backend] Loc: Bengaluru",
            source=source,
            priority="Priority A",
            score=18.5,
            role_family="SDE / Backend",
        )

        # First run: add real match
        self.handler.update_matches([match_real])

        # Simulate user writing notes and status in Excel
        wb = openpyxl.load_workbook(self.wb_path)
        ws = wb["Matches"]
        
        # Add a demo fake row with 'example' URL to test clean_demo_data
        demo_row = ws.max_row + 1
        ws.cell(row=demo_row, column=3, value="GitLab")
        ws.cell(row=demo_row, column=4, value="Demo Job")
        ws.cell(row=demo_row, column=6, value="https://boards.greenhouse.io/gitlab/jobs/example")
        
        # User modifies real job
        target_row = None
        for r in range(2, ws.max_row + 1):
            if ws.cell(row=r, column=6).value == "https://job-boards.greenhouse.io/razorpay/jobs/real-101":
                target_row = r
                break
        self.assertIsNotNone(target_row)
        ws.cell(row=target_row, column=11, value="Interview Scheduled")
        ws.cell(row=target_row, column=12, value="Connected with tech lead on LinkedIn")
        wb.save(self.wb_path)
        wb.close()

        # Clean demo data
        self.handler.clean_demo_data()

        # Verify demo row was removed and real job preserved
        wb_clean = openpyxl.load_workbook(self.wb_path)
        ws_clean = wb_clean["Matches"]
        urls = [ws_clean.cell(row=r, column=6).value for r in range(2, ws_clean.max_row + 1)]
        self.assertNotIn("https://boards.greenhouse.io/gitlab/jobs/example", urls)
        self.assertIn("https://job-boards.greenhouse.io/razorpay/jobs/real-101", urls)
        
        for r in range(2, ws_clean.max_row + 1):
            if ws_clean.cell(row=r, column=6).value == "https://job-boards.greenhouse.io/razorpay/jobs/real-101":
                self.assertEqual(ws_clean.cell(row=r, column=11).value, "Interview Scheduled")
                self.assertEqual(ws_clean.cell(row=r, column=12).value, "Connected with tech lead on LinkedIn")
        wb_clean.close()


class TestFetcherRegistry(unittest.TestCase):
    def test_registry_dispatch(self):
        f1 = FetcherRegistry.get_fetcher_for_url("https://www.amazon.jobs/en/search.json", "test-agent")
        self.assertIsInstance(f1, AmazonFetcher)

        f2 = FetcherRegistry.get_fetcher_for_url("https://postman.wd108.myworkdayjobs.com/careers", "test-agent")
        self.assertIsInstance(f2, WorkdayFetcher)

        f3 = FetcherRegistry.get_fetcher_for_url("https://boards.greenhouse.io/razorpay", "test-agent")
        self.assertIsInstance(f3, GreenhouseFetcher)


if __name__ == "__main__":
    unittest.main()
