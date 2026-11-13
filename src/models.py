"""Data models for the job search monitor."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class JobSource:
    """Represents a target company and search criteria from the Sources sheet."""
    company_name: str
    careers_url: str
    priority: str = "Priority A"  # "Priority A" or "Priority B"
    target_titles: List[str] = field(default_factory=list)
    location_preferences: List[str] = field(default_factory=list)
    experience_range: str = "0-2 years"
    include_keywords: List[str] = field(default_factory=list)
    exclude_keywords: List[str] = field(default_factory=list)
    active: bool = True
    review_notes: str = ""  # Reason if source needs review or manual check


@dataclass
class JobListing:
    """Represents a job listing fetched from an ATS, API, or webpage."""
    company: str
    title: str
    location: str
    url: str
    posted_date: Optional[str] = None  # Format: YYYY-MM-DD if available
    description: Optional[str] = None
    department: Optional[str] = None
    priority: str = "Priority A"


@dataclass
class MatchResult:
    """Represents a job listing that passed matching criteria."""
    job: JobListing
    matched_criteria: str
    source: JobSource
    priority: str = "Priority A"
    score: float = 0.0
    role_family: str = ""  # "SDE / Backend" or "SRE / DevOps"
    match_status: str = "Confirmed"  # "Confirmed" or "Needs experience review"
    experience_text: str = ""  # Exact extracted experience text


@dataclass
class ExcludedListing:
    """Represents a job listing excluded during experience evaluation (e.g. 2+ years)."""
    company: str
    title: str
    location: str
    url: str
    reason: str
    experience_text: str = ""
    priority: str = "Priority A"


@dataclass
class EvaluationOutcome:
    """Outcome of evaluating a single job listing."""
    status: str  # 'CONFIRMED', 'NEEDS_REVIEW', 'EXCLUDED_2PLUS', 'DISQUALIFIED'
    match_result: Optional[MatchResult] = None
    excluded_listing: Optional[ExcludedListing] = None
    reason: str = ""
    experience_text: str = ""


@dataclass
class SourceRunResult:
    """Summary of a fetch attempt for a single source."""
    company_name: str
    careers_url: str
    priority: str = "Priority A"
    status: str = "SUCCESS"  # 'SUCCESS', 'EMPTY', 'RESTRICTED', 'NEEDS_REVIEW', 'FAILED'
    total_found: int = 0
    matched_count: int = 0
    error_message: Optional[str] = None


@dataclass
class DailyRunSummary:
    """Aggregated report of the daily monitoring execution."""
    started_at: datetime
    finished_at: datetime
    total_sources: int = 0
    active_sources: int = 0
    successful_sources: int = 0
    failed_sources: int = 0
    needs_review_sources: int = 0
    total_listings_scanned: int = 0
    new_matches_added: int = 0
    existing_matches_updated: int = 0
    source_results: List[SourceRunResult] = field(default_factory=list)
    confirmed_matches: List[MatchResult] = field(default_factory=list)
    review_needed_matches: List[MatchResult] = field(default_factory=list)
    excluded_listings_2plus: List[ExcludedListing] = field(default_factory=list)
