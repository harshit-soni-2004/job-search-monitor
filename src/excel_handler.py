"""Excel handler to manage Sources and Matches sheets without overwriting user data."""

from datetime import datetime
import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from src.models import ExcludedListing, JobListing, JobSource, MatchResult
from src.watchlist import (
    DEFAULT_EXP_RANGE,
    DEFAULT_EXCLUDE_KEYWORDS,
    DEFAULT_INCLUDE_KEYWORDS,
    DEFAULT_LOCATIONS,
    DEFAULT_TARGET_TITLES,
    WATCHLIST,
)


class ExcelHandler:
    """Manages reading and writing job search data in an Excel workbook."""

    STANDARD_SOURCES_HEADERS = [
        "Priority",
        "Company Name",
        "Careers URL",
        "Target Titles",
        "Location Preferences",
        "Experience Range",
        "Include Keywords",
        "Exclude Keywords",
        "Active",
        "Notes / Review",
    ]

    STANDARD_MATCHES_HEADERS = [
        "Priority",
        "Score",
        "Company",
        "Job Title",
        "Location",
        "Job URL",
        "Posted Date",
        "Matched Criteria",
        "First-Seen Date",
        "Last-Checked Date",
        "Status",
        "Notes",
    ]

    STANDARD_EXCLUDED_HEADERS = [
        "Company",
        "Job Title",
        "Location",
        "Job URL",
        "Exclusion Reason",
        "Stated Experience Text",
        "Date Logged",
        "Priority",
    ]

    def __init__(self, workbook_path: str | Path):
        self.workbook_path = Path(workbook_path)

    @staticmethod
    def _normalize_url(url: str) -> str:
        if not url:
            return ""
        return url.strip().rstrip("/")

    def ensure_workbook_exists(self):
        """Creates a template workbook if it does not already exist."""
        if not self.workbook_path.exists():
            self.create_template_workbook()

    def clean_demo_data(self):
        """Removes only clearly identified demo listings (e.g. test matches with '/jobs/example' or fake demo URLs)."""
        if not self.workbook_path.exists():
            return

        wb = openpyxl.load_workbook(self.workbook_path)
        if "Matches" not in wb.sheetnames:
            wb.close()
            return

        ws = wb["Matches"]
        url_col = None
        for col_idx in range(1, ws.max_column + 1):
            val = ws.cell(row=1, column=col_idx).value
            if val and "url" in str(val).lower():
                url_col = col_idx
                break

        if not url_col:
            wb.close()
            return

        rows_to_delete = []
        for r in range(2, ws.max_row + 1):
            url_val = str(ws.cell(row=r, column=url_col).value or "").strip().lower()
            # Identify the specific demo test match
            is_demo = (
                url_val.endswith("/jobs/example")
                or url_val.endswith("/jobs/example/")
                or "/example" in url_val
                or "demo_test_job" in url_val
                or url_val == "https://boards.greenhouse.io/gitlab/jobs/example"
            )
            if is_demo:
                rows_to_delete.append(r)

        # Delete rows bottom-up to preserve index alignment
        for r in reversed(rows_to_delete):
            ws.delete_rows(r)

        wb.save(self.workbook_path)
        wb.close()

    def populate_watchlist(self):
        """
        Populate or update the Sources sheet with the full India watchlist.
        Preserves any existing user-added companies, modifications, and formatting.
        """
        self.ensure_workbook_exists()
        wb = openpyxl.load_workbook(self.workbook_path)
        
        if "Sources" not in wb.sheetnames:
            ws = wb.create_sheet(title="Sources", index=0)
        else:
            ws = wb["Sources"]

        # Map headers
        header_to_col: Dict[str, int] = {}
        for c in range(1, ws.max_column + 1):
            val = ws.cell(row=1, column=c).value
            if val:
                header_to_col[str(val).strip().lower()] = c

        # If headers are missing, write standard headers
        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
        thin_border = Border(
            left=Side(style="thin", color="D9D9D9"),
            right=Side(style="thin", color="D9D9D9"),
            top=Side(style="thin", color="D9D9D9"),
            bottom=Side(style="thin", color="D9D9D9"),
        )
        center_align = Alignment(horizontal="center", vertical="center")
        left_align = Alignment(horizontal="left", vertical="center")

        def ensure_header(name: str) -> int:
            normalized = name.lower()
            if normalized in header_to_col:
                return header_to_col[normalized]
            next_col = ws.max_column + 1
            cell = ws.cell(row=1, column=next_col, value=name)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_align
            cell.border = thin_border
            header_to_col[normalized] = next_col
            return next_col

        col_priority = ensure_header("Priority")
        col_company = ensure_header("Company Name")
        col_url = ensure_header("Careers URL")
        col_titles = ensure_header("Target Titles")
        col_locations = ensure_header("Location Preferences")
        col_exp = ensure_header("Experience Range")
        col_includes = ensure_header("Include Keywords")
        col_excludes = ensure_header("Exclude Keywords")
        col_active = ensure_header("Active")
        col_notes = ensure_header("Notes / Review")

        # Map existing companies
        existing_companies: Dict[str, int] = {}
        for r in range(2, ws.max_row + 1):
            val = ws.cell(row=r, column=col_company).value
            if val:
                existing_companies[str(val).strip().lower()] = r

        body_font = Font(name="Segoe UI", size=10)

        # Merge watchlist
        for entry in WATCHLIST:
            comp_name = entry["company"]
            comp_key = comp_name.strip().lower()

            if comp_key in existing_companies:
                # Update Priority and review notes if missing, preserve everything else
                r = existing_companies[comp_key]
                if not ws.cell(row=r, column=col_priority).value:
                    ws.cell(row=r, column=col_priority, value=entry["priority"])
                if not ws.cell(row=r, column=col_notes).value and entry.get("review_notes"):
                    ws.cell(row=r, column=col_notes, value=entry["review_notes"])
            else:
                # Append new row
                r = ws.max_row + 1
                existing_companies[comp_key] = r

                ws.cell(row=r, column=col_priority, value=entry["priority"])
                ws.cell(row=r, column=col_company, value=comp_name)
                ws.cell(row=r, column=col_url, value=entry["url"])
                ws.cell(row=r, column=col_titles, value=DEFAULT_TARGET_TITLES)
                ws.cell(row=r, column=col_locations, value=DEFAULT_LOCATIONS)
                ws.cell(row=r, column=col_exp, value=DEFAULT_EXP_RANGE)
                ws.cell(row=r, column=col_includes, value=DEFAULT_INCLUDE_KEYWORDS)
                ws.cell(row=r, column=col_excludes, value=DEFAULT_EXCLUDE_KEYWORDS)
                ws.cell(row=r, column=col_active, value=entry.get("active", "Yes"))
                ws.cell(row=r, column=col_notes, value=entry.get("review_notes", ""))

                for c in range(1, ws.max_column + 1):
                    cell = ws.cell(row=r, column=c)
                    cell.font = body_font
                    cell.border = thin_border
                    if c in (col_priority, col_active):
                        cell.alignment = center_align
                    else:
                        cell.alignment = left_align

        # Auto-adjust column widths
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(min(max_len + 4, 45), 14)

        wb.save(self.workbook_path)
        wb.close()

    def create_template_workbook(self):
        """Generate a well-formatted template Excel workbook with full India watchlist."""
        wb = openpyxl.Workbook()
        ws_sources = wb.active
        ws_sources.title = "Sources"
        ws_matches = wb.create_sheet(title="Matches")

        # Initialize Matches headers
        matches_fill = PatternFill(start_color="2E75B6", end_color="2E75B6", fill_type="solid")
        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        thin_border = Border(
            left=Side(style="thin", color="D9D9D9"),
            right=Side(style="thin", color="D9D9D9"),
            top=Side(style="thin", color="D9D9D9"),
            bottom=Side(style="thin", color="D9D9D9"),
        )
        center_align = Alignment(horizontal="center", vertical="center")

        for c_idx, h_text in enumerate(self.STANDARD_MATCHES_HEADERS, 1):
            cell = ws_matches.cell(row=1, column=c_idx, value=h_text)
            cell.font = header_font
            cell.fill = matches_fill
            cell.alignment = center_align
            cell.border = thin_border

        wb.save(self.workbook_path)
        wb.close()
        self.populate_watchlist()

    def load_sources(self) -> List[JobSource]:
        """Read all active job search sources from the Sources sheet, ordered by Priority."""
        self.ensure_workbook_exists()
        wb = openpyxl.load_workbook(self.workbook_path, data_only=True)

        if "Sources" not in wb.sheetnames:
            raise ValueError(f"Workbook '{self.workbook_path}' does not contain a 'Sources' sheet.")

        ws = wb["Sources"]
        headers: Dict[str, int] = {}
        for col_idx in range(1, ws.max_column + 1):
            val = ws.cell(row=1, column=col_idx).value
            if val:
                headers[str(val).strip().lower()] = col_idx

        def _get_val(row_idx: int, field_name: str) -> str:
            col = headers.get(field_name.lower())
            if not col:
                return ""
            val = ws.cell(row=row_idx, column=col).value
            return str(val).strip() if val is not None else ""

        def _split_list(text: str) -> List[str]:
            if not text:
                return []
            return [p.strip() for p in text.replace(";", ",").split(",") if p.strip()]

        sources: List[JobSource] = []
        for r in range(2, ws.max_row + 1):
            company = _get_val(r, "Company Name") or _get_val(r, "Company")
            url = _get_val(r, "Careers URL") or _get_val(r, "URL")
            if not company or not url:
                continue

            active_str = _get_val(r, "Active").lower()
            is_active = active_str in ("yes", "true", "1", "active")

            priority_val = _get_val(r, "Priority") or "Priority A"
            review_notes = _get_val(r, "Notes / Review") or _get_val(r, "Notes")

            source = JobSource(
                company_name=company,
                careers_url=url,
                priority=priority_val,
                target_titles=_split_list(_get_val(r, "Target Titles") or _get_val(r, "Titles")),
                location_preferences=_split_list(_get_val(r, "Location Preferences") or _get_val(r, "Location")),
                experience_range=_get_val(r, "Experience Range") or _get_val(r, "Experience"),
                include_keywords=_split_list(_get_val(r, "Include Keywords") or _get_val(r, "Keywords")),
                exclude_keywords=_split_list(_get_val(r, "Exclude Keywords") or _get_val(r, "Exclude")),
                active=is_active,
                review_notes=review_notes,
            )
            sources.append(source)

        wb.close()
        
        # Priority A first, then Priority B
        sources.sort(key=lambda s: (0 if "Priority A" in s.priority else 1, s.company_name))
        return sources

    def update_matches(self, matches: List[MatchResult]) -> Tuple[int, int]:
        """
        Update the Matches sheet with new listings and update last-checked dates.
        CRITICAL GUARANTEE: Never overwrites user notes, application status, or custom columns!
        Returns (new_matches_added, existing_matches_updated).
        """
        self.ensure_workbook_exists()
        wb = openpyxl.load_workbook(self.workbook_path)

        if "Matches" not in wb.sheetnames:
            ws = wb.create_sheet(title="Matches")
        else:
            ws = wb["Matches"]

        # Map existing headers in Matches sheet
        header_to_col: Dict[str, int] = {}
        for col_idx in range(1, ws.max_column + 1):
            val = ws.cell(row=1, column=col_idx).value
            if val is not None and str(val).strip():
                header_name = str(val).strip()
                header_to_col[header_name.lower()] = col_idx

        # Style helpers
        matches_fill = PatternFill(start_color="2E75B6", end_color="2E75B6", fill_type="solid")
        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        thin_border = Border(
            left=Side(style="thin", color="D9D9D9"),
            right=Side(style="thin", color="D9D9D9"),
            top=Side(style="thin", color="D9D9D9"),
            bottom=Side(style="thin", color="D9D9D9"),
        )
        center_align = Alignment(horizontal="center", vertical="center")
        left_align = Alignment(horizontal="left", vertical="center")

        # If sheet was empty or had no valid headers, write all standard headers from column 1
        if not header_to_col:
            for c_idx, h_name in enumerate(self.STANDARD_MATCHES_HEADERS, 1):
                cell = ws.cell(row=1, column=c_idx, value=h_name)
                cell.font = header_font
                cell.fill = matches_fill
                cell.alignment = center_align
                cell.border = thin_border
                header_to_col[h_name.lower()] = c_idx

        def get_col(name: str) -> int:
            normalized = name.lower()
            if normalized in header_to_col:
                return header_to_col[normalized]
            next_col = max(header_to_col.values(), default=0) + 1
            cell = ws.cell(row=1, column=next_col, value=name)
            cell.font = header_font
            cell.fill = matches_fill
            cell.alignment = center_align
            cell.border = thin_border
            header_to_col[normalized] = next_col
            return next_col

        col_priority = get_col("Priority")
        col_score = get_col("Score")
        col_company = get_col("Company")
        col_title = get_col("Job Title")
        col_location = get_col("Location")
        col_url = get_col("Job URL")
        col_posted = get_col("Posted Date")
        col_criteria = get_col("Matched Criteria")
        col_first_seen = get_col("First-Seen Date")
        col_last_checked = get_col("Last-Checked Date")
        col_status = get_col("Status")
        col_notes = get_col("Notes")

        # Build index of existing rows by normalized Job URL
        existing_url_to_row: Dict[str, int] = {}
        for r in range(2, ws.max_row + 1):
            url_val = ws.cell(row=r, column=col_url).value
            if url_val:
                norm_url = self._normalize_url(str(url_val))
                if norm_url:
                    existing_url_to_row[norm_url] = r

        today_str = datetime.now().strftime("%Y-%m-%d")
        new_added = 0
        existing_updated = 0
        body_font = Font(name="Segoe UI", size=10)

        # Sort matches so highest scoring roles are inserted
        sorted_matches = sorted(matches, key=lambda m: m.score, reverse=True)

        for match in sorted_matches:
            job = match.job
            norm_url = self._normalize_url(job.url)
            if not norm_url:
                continue

            if norm_url in existing_url_to_row:
                # EXISTING LISTING: Update only Last-Checked, Score, and Priority
                row_idx = existing_url_to_row[norm_url]
                ws.cell(row=row_idx, column=col_last_checked, value=today_str)
                ws.cell(row=row_idx, column=col_score, value=match.score)
                ws.cell(row=row_idx, column=col_priority, value=match.priority)
                if job.posted_date:
                    current_posted = ws.cell(row=row_idx, column=col_posted).value
                    if not current_posted:
                        ws.cell(row=row_idx, column=col_posted, value=job.posted_date)
                
                # GUARANTEE: Status and Notes are deliberately NOT touched!
                existing_updated += 1
            else:
                # NEW LISTING
                new_row_idx = ws.max_row + 1
                existing_url_to_row[norm_url] = new_row_idx

                ws.cell(row=new_row_idx, column=col_priority, value=match.priority)
                ws.cell(row=new_row_idx, column=col_score, value=match.score)
                ws.cell(row=new_row_idx, column=col_company, value=job.company)
                ws.cell(row=new_row_idx, column=col_title, value=job.title)
                ws.cell(row=new_row_idx, column=col_location, value=job.location)
                ws.cell(row=new_row_idx, column=col_url, value=job.url)
                ws.cell(row=new_row_idx, column=col_posted, value=job.posted_date or "")
                ws.cell(row=new_row_idx, column=col_criteria, value=match.matched_criteria)
                ws.cell(row=new_row_idx, column=col_first_seen, value=today_str)
                ws.cell(row=new_row_idx, column=col_last_checked, value=today_str)
                ws.cell(row=new_row_idx, column=col_status, value=match.match_status or "Confirmed")
                ws.cell(row=new_row_idx, column=col_notes, value=match.experience_text or "")

                for c in range(1, ws.max_column + 1):
                    cell = ws.cell(row=new_row_idx, column=c)
                    cell.font = body_font
                    cell.border = thin_border
                    if c in (col_priority, col_score, col_posted, col_first_seen, col_last_checked, col_status):
                        cell.alignment = center_align
                    else:
                        cell.alignment = left_align

                new_added += 1

        wb.save(self.workbook_path)
        wb.close()
        return new_added, existing_updated

    def update_excluded(self, excluded_list: List[ExcludedListing]) -> int:
        """
        Record listings excluded due to 2+ years into a clearly labeled 'Excluded' sheet.
        Returns number of newly added excluded entries.
        """
        if not excluded_list:
            return 0

        self.ensure_workbook_exists()
        wb = openpyxl.load_workbook(self.workbook_path)

        if "Excluded" not in wb.sheetnames:
            ws = wb.create_sheet(title="Excluded")
            header_fill = PatternFill(start_color="A61C1C", end_color="A61C1C", fill_type="solid")
            header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
            thin_border = Border(
                left=Side(style="thin", color="D9D9D9"),
                right=Side(style="thin", color="D9D9D9"),
                top=Side(style="thin", color="D9D9D9"),
                bottom=Side(style="thin", color="D9D9D9"),
            )
            center_align = Alignment(horizontal="center", vertical="center")

            for c_idx, h_text in enumerate(self.STANDARD_EXCLUDED_HEADERS, 1):
                cell = ws.cell(row=1, column=c_idx, value=h_text)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = center_align
                cell.border = thin_border
        else:
            ws = wb["Excluded"]

        existing_urls = set()
        for r in range(2, ws.max_row + 1):
            val = ws.cell(row=r, column=4).value
            if val:
                existing_urls.add(self._normalize_url(str(val)))

        today_str = datetime.now().strftime("%Y-%m-%d")
        body_font = Font(name="Segoe UI", size=10)
        thin_border = Border(
            left=Side(style="thin", color="D9D9D9"),
            right=Side(style="thin", color="D9D9D9"),
            top=Side(style="thin", color="D9D9D9"),
            bottom=Side(style="thin", color="D9D9D9"),
        )
        added_count = 0

        for item in excluded_list:
            norm_url = self._normalize_url(item.url)
            if not norm_url or norm_url in existing_urls:
                continue

            r_idx = ws.max_row + 1
            existing_urls.add(norm_url)

            ws.cell(row=r_idx, column=1, value=item.company)
            ws.cell(row=r_idx, column=2, value=item.title)
            ws.cell(row=r_idx, column=3, value=item.location)
            ws.cell(row=r_idx, column=4, value=item.url)
            ws.cell(row=r_idx, column=5, value=item.reason)
            ws.cell(row=r_idx, column=6, value=item.experience_text)
            ws.cell(row=r_idx, column=7, value=today_str)
            ws.cell(row=r_idx, column=8, value=item.priority)

            for c in range(1, 9):
                cell = ws.cell(row=r_idx, column=c)
                cell.font = body_font
                cell.border = thin_border
                if c in (7, 8):
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="center")

            added_count += 1

        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(min(max_len + 4, 60), 14)

        wb.save(self.workbook_path)
        wb.close()
        return added_count
