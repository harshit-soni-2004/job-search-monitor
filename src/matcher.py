"""Enhanced matching engine with role families, India locations, and strict experience filtering."""

import html
import re
from typing import List, Optional, Tuple
from src.models import EvaluationOutcome, ExcludedListing, JobListing, JobSource, MatchResult


class JobMatcher:
    """Evaluates and ranks job listings against user criteria, role families, and strict experience rules."""

    # Role Families
    ROLE_FAMILY_SDE = "SDE / Backend"
    ROLE_FAMILY_SRE = "SRE / DevOps"

    SDE_PATTERNS = [
        r"associate\s+software\s+engineer",
        r"software\s+engineer\s+(?:i|1|e1)\b",
        r"sde\s*(?:i|1|-i|-1)\b",
        r"backend\s+engineer",
        r"java\s+developer",
        r"java\s+backend\s+engineer",
        r"spring\s+boot\s+engineer",
        r"platform\s+engineer",
        r"software\s+development\s+engineer\s*(?:i|1)?\b",
        r"software\s+engineer\b",
    ]

    SRE_PATTERNS = [
        r"(?:junior|associate)?\s*sre\s*(?:i|1|-i|-1)?\b",
        r"site\s+reliability\s+engineer",
        r"devops\s+engineer",
        r"cloud\s+(?:infrastructure\s+)?engineer",
        r"infrastructure\s+engineer",
        r"platform\s+engineer",
        r"production\s+engineer",
        r"build\s*(?:&|and)?\s*release\s+engineer",
        r"release\s+engineer",
    ]

    # Explicit disqualifications
    INTERN_REGEX = re.compile(
        r"(?<!non[- ])\b(intern|internship|co-?op|trainee|apprentice|student|fellowship)\b",
        re.IGNORECASE,
    )
    SENIOR_REGEX = re.compile(
        r"\b(senior|sr\b|sr\.|staff|principal|lead|leader|manager|director|vp|vice\s+president|head|architect|chief|partner)\b",
        re.IGNORECASE,
    )
    MID_SENIOR_LEVEL_REGEX = re.compile(
        r"\b(?:sde|software\s+(?:development\s+)?engineer|backend\s+engineer|developer|sre|platform\s+engineer)\s*(?:ii|iii|iv|2|3|4)\b",
        re.IGNORECASE,
    )

    # 2+ years experience exclusion patterns (phrases such as "2+ years", "2-4 years", "minimum 2 years", etc.)
    EXCLUDE_2PLUS_REGEX = re.compile(
        r"("
        r"\b(?:[2-9]|\d{2,})\+?\s*(?:to|-)\s*\d+\s*(?:years?|yrs?)\b|"
        r"\b(?:minimum|min|at\s+least)\s+(?:[2-9]|\d{2,}|two|three|four|five)\s*(?:\+)?\s*(?:years?|yrs?)\b|"
        r"\b(?:two|[2-9]|\d{2,})\s+or\s+more\s+years\b|"
        r"\b(?:[2-9]|\d{2,})\s*\+\s*(?:years?|yrs?)\b|"
        r"\b(?:[2-9]|\d{2,})\s+(?:years?|yrs?)\s+(?:of\s+)?(?:experience|exp|hands-on|industry|professional|relevant|software)\b"
        r")",
        re.IGNORECASE,
    )

    # 0-1 years / fresher / graduate acceptance patterns
    ACCEPT_0TO1_REGEX = re.compile(
        r"("
        r"\b(?:0\s*(?:to|-)\s*1|0\s*(?:to|-)\s*2)\s*(?:years?|yrs?)\b|"
        r"\b(?:0|1)\s*\+\s*(?:years?|yrs?)\b|"
        r"\b(?:minimum|min|at\s+least)\s+(?:0|1|one)\s*(?:years?|yrs?)\b|"
        r"\b(?:0|1|one)\s+(?:years?|yrs?)\s+(?:of\s+)?(?:experience|exp|hands-on|industry|professional|relevant|software)\b|"
        r"\b(?:up\s+to|maximum|max|under)\s+(?:1|2|one|two)\s*(?:years?|yrs?)\b|"
        r"\b(fresher|freshers|fresh\s+graduate|recent\s+graduate|recent\s+graduates|college\s+graduate|university\s+graduate|new\s+grad|new\s+grads|campus\s+hire|campus\s+recruitment|entry\s+level|entry-level)\b"
        r")",
        re.IGNORECASE,
    )

    # India location preferences
    TIER1_INDIA = ["bengaluru", "bangalore", "hyderabad", "mumbai", "delhi", "ncr", "gurugram", "gurgaon", "noida"]
    TIER2_INDIA = ["pune", "chennai", "kolkata", "ahmedabad", "kochi", "trivandrum", "jaipur", "chandigarh", "india"]
    
    FOREIGN_LOCATIONS = [
        "united states", "us only", "usa", "united kingdom", "uk only", "canada",
        "europe", "germany", "australia", "singapore", "poland", "ireland", "japan"
    ]

    # User skills ranking weights
    CORE_SKILLS = {
        "java 21": 3.5,
        "java": 3.0,
        "spring boot": 3.0,
        "spring": 2.0,
        "rest api": 2.5,
        "rest": 2.0,
        "kubernetes": 3.0,
        "eks": 3.0,
        "docker": 2.5,
        "aws": 2.5,
        "terraform": 2.5,
        "linux": 2.0,
        "bash": 2.0,
        "python": 2.0,
        "ci/cd": 2.0,
        "systemd": 1.5,
        "mysql": 2.0,
        "redis": 2.5,
        "rabbitmq": 2.5,
    }

    BONUS_OBSERVABILITY = {
        "prometheus": 1.5,
        "grafana": 1.5,
        "elk": 1.5,
        "elasticsearch": 1.5,
        "logstash": 1.0,
        "kibana": 1.0,
        "opentelemetry": 1.5,
        "datadog": 1.0,
        "jaeger": 1.0,
    }

    @staticmethod
    def _word_match(pattern: str, text: str) -> bool:
        if not pattern or not text:
            return False
        escaped = re.escape(pattern.strip().lower())
        # Do not match "intern" / "internship" if preceded by "non-" or "non "
        if pattern.strip().lower() in ("intern", "internship", "co-op", "trainee"):
            return bool(re.search(rf"(?<!non[- ])\b{escaped}\b", text.lower()))
        return bool(re.search(rf"\b{escaped}\b", text.lower()))

    @staticmethod
    def _extract_snippet(text: str, match_obj: re.Match, max_len: int = 160) -> str:
        """Extract clean sentence or bullet containing regex match."""
        if not match_obj or not text:
            return ""
        start, end = match_obj.span()
        left = text.rfind("\n", 0, start)
        if left == -1:
            left = text.rfind(". ", 0, start)
            left = left + 2 if left != -1 else 0
        else:
            left = left + 1

        right = text.find("\n", end)
        if right == -1:
            right = text.find(". ", end)
            right = right + 1 if right != -1 else len(text)

        snippet = text[left:right].strip(" -*•\t\r")
        if len(snippet) > max_len:
            snippet = snippet[:max_len] + "..."
        return snippet

    def evaluate_listing(self, job: JobListing, source: JobSource) -> EvaluationOutcome:
        """
        Evaluate a job listing under strict early-career criteria (~1 year exp):
        - Disqualify internships, senior roles, or irrelevant locations.
        - Exclude if explicitly requires >= 2 years ("2+ years", "2-4 years", "minimum 2 years").
        - Mark 'Needs experience review' if experience requirement is missing/ambiguous.
        - Mark 'Confirmed' ONLY if stated minimum experience is 0-1 years or explicitly accepts freshers/graduates.
        """
        title = job.title or ""
        desc = job.description or ""
        loc = job.location or ""
        full_text = f"{title} {loc} {job.department or ''} {desc}"

        # 1. IMMEDIATE DISQUALIFICATIONS
        # Reject Internships
        if self.INTERN_REGEX.search(title) or (desc and self.INTERN_REGEX.search(desc[:300])):
            return EvaluationOutcome(status="DISQUALIFIED", reason="Internship / trainee role")

        # Reject Senior / Lead / Principal / Manager
        if self.SENIOR_REGEX.search(title):
            return EvaluationOutcome(status="DISQUALIFIED", reason="Senior / Lead / Manager title")

        # 2. ROLE FAMILY MATCHING (Must match SDE/Backend or SRE/DevOps)
        role_family = None
        for pat in self.SRE_PATTERNS:
            if re.search(pat, title, re.IGNORECASE):
                role_family = self.ROLE_FAMILY_SRE
                break

        if not role_family:
            for pat in self.SDE_PATTERNS:
                if re.search(pat, title, re.IGNORECASE):
                    role_family = self.ROLE_FAMILY_SDE
                    break

        if not role_family and source.target_titles:
            for t in source.target_titles:
                if self._word_match(t, title):
                    role_family = self.ROLE_FAMILY_SDE
                    break

        if not role_family:
            return EvaluationOutcome(status="DISQUALIFIED", reason="Role title does not match target role families")

        # 3. LOCATION FILTERING (India Preference)
        loc_lower = loc.lower()
        full_loc_text = f"{loc_lower} {title.lower()}"

        is_foreign = any(f in loc_lower for f in self.FOREIGN_LOCATIONS)
        has_india = any(c in full_loc_text for c in self.TIER1_INDIA + self.TIER2_INDIA)
        is_global_remote = "remote" in loc_lower and not is_foreign

        if is_foreign and not has_india:
            return EvaluationOutcome(status="DISQUALIFIED", reason="Foreign-only location")

        location_tier = 0
        matched_city = "India / Remote"
        for city in self.TIER1_INDIA:
            if city in full_loc_text:
                location_tier = 1
                matched_city = city.capitalize()
                break

        if location_tier == 0:
            for city in self.TIER2_INDIA:
                if city in full_loc_text:
                    location_tier = 2
                    matched_city = city.capitalize()
                    break

        if location_tier == 0 and not is_global_remote and "india" not in loc_lower and loc.strip() != "":
            if not any(source_loc.lower() in loc_lower for source_loc in source.location_preferences):
                return EvaluationOutcome(status="DISQUALIFIED", reason="Location outside India target criteria")

        # 4. STRICT EXPERIENCE FILTERING
        # Check A: Exclude if numbered level indicates mid/senior (e.g. SDE II, Software Engineer 2)
        if self.MID_SENIOR_LEVEL_REGEX.search(title):
            return EvaluationOutcome(
                status="EXCLUDED_2PLUS",
                excluded_listing=ExcludedListing(
                    company=job.company,
                    title=job.title,
                    location=job.location,
                    url=job.url,
                    reason=f"Mid/Senior level title: '{title}'",
                    experience_text=title,
                    priority=source.priority,
                ),
                reason=f"Mid/Senior level title: '{title}'",
                experience_text=title,
            )

        # Check B: Exclude if description or title explicitly requires 2+ years
        m_2plus = self.EXCLUDE_2PLUS_REGEX.search(desc or "") or self.EXCLUDE_2PLUS_REGEX.search(title)
        if m_2plus:
            snippet = self._extract_snippet(desc if self.EXCLUDE_2PLUS_REGEX.search(desc or "") else title, m_2plus)
            return EvaluationOutcome(
                status="EXCLUDED_2PLUS",
                excluded_listing=ExcludedListing(
                    company=job.company,
                    title=job.title,
                    location=job.location,
                    url=job.url,
                    reason=f"Explicitly requires 2+ years: '{snippet}'",
                    experience_text=snippet,
                    priority=source.priority,
                ),
                reason=f"Explicitly requires 2+ years: '{snippet}'",
                experience_text=snippet,
            )

        # 5. SKILLS SCORING & AUDIT
        score = 0.0
        priority_val = source.priority or "Priority A"
        score += 5.0 if "Priority A" in priority_val else 2.0

        if location_tier == 1:
            score += 3.0
        elif location_tier == 2 or is_global_remote:
            score += 2.0

        matched_skills: List[str] = []
        full_lower = full_text.lower()
        for skill, weight in self.CORE_SKILLS.items():
            if self._word_match(skill, full_lower):
                matched_skills.append(skill.title())
                score += weight

        matched_observability: List[str] = []
        for obs_tool, weight in self.BONUS_OBSERVABILITY.items():
            if self._word_match(obs_tool, full_lower):
                matched_observability.append(obs_tool.title())
                score += weight

        # Check custom source exclusions
        for excl in source.exclude_keywords:
            excl_clean = excl.strip()
            if excl_clean and (self._word_match(excl_clean, title) or (desc and self._word_match(excl_clean, desc))):
                return EvaluationOutcome(status="DISQUALIFIED", reason=f"Custom exclude keyword: '{excl_clean}'")

        # Check C: Check for explicit 0-1 years or fresher/graduate requirement
        m_0to1 = self.ACCEPT_0TO1_REGEX.search(desc or "")
        if m_0to1:
            snippet_0to1 = self._extract_snippet(desc, m_0to1)
            reasons = [
                f"[{role_family}]",
                f"Loc: {matched_city}",
                f"Exp: {snippet_0to1}",
            ]
            if matched_skills:
                reasons.append(f"Skills: {', '.join(matched_skills[:4])}")
            if matched_observability:
                reasons.append(f"Bonus: {', '.join(matched_observability[:2])}")

            match_res = MatchResult(
                job=job,
                matched_criteria=" | ".join(reasons),
                source=source,
                priority=priority_val,
                score=round(score + 3.0, 1),
                role_family=role_family,
                match_status="Confirmed",
                experience_text=snippet_0to1,
            )
            return EvaluationOutcome(
                status="CONFIRMED",
                match_result=match_res,
                reason=f"Confirmed match (0-1 yr stated experience: '{snippet_0to1}')",
                experience_text=snippet_0to1,
            )

        # Check D: Experience missing, ambiguous, or only on application page
        # Rule: Do not classify role as suitable based only on title "SDE I" or "Software Engineer"
        exp_reason = "Experience requirement not stated on public listing page / only shown on employer portal"
        reasons = [
            f"[{role_family}]",
            f"Loc: {matched_city}",
            "Exp: Unverified (Needs Review)",
        ]
        if matched_skills:
            reasons.append(f"Skills: {', '.join(matched_skills[:4])}")

        match_res = MatchResult(
            job=job,
            matched_criteria=" | ".join(reasons),
            source=source,
            priority=priority_val,
            score=round(score, 1),
            role_family=role_family,
            match_status="Needs experience review",
            experience_text=exp_reason,
        )
        return EvaluationOutcome(
            status="NEEDS_REVIEW",
            match_result=match_res,
            reason=exp_reason,
            experience_text=exp_reason,
        )

    def evaluate(self, job: JobListing, source: JobSource) -> Optional[MatchResult]:
        """Convenience method returning MatchResult if Confirmed or Needs Review (None if Disqualified or Excluded)."""
        outcome = self.evaluate_listing(job, source)
        if outcome.status in ("CONFIRMED", "NEEDS_REVIEW"):
            return outcome.match_result
        return None
