"""Fetcher registry to dispatch career URLs to specialized ATS or generic fetchers."""

import logging
from typing import Optional
from urllib.parse import urlparse

from src.fetcher.amazon import AmazonFetcher
from src.fetcher.ashby import AshbyFetcher
from src.fetcher.base import BaseFetcher
from src.fetcher.generic import GenericFetcher
from src.fetcher.greenhouse import GreenhouseFetcher
from src.fetcher.lever import LeverFetcher
from src.fetcher.smartrecruiters import SmartRecruitersFetcher
from src.fetcher.tinyfish import TinyFishFetcher
from src.fetcher.workable import WorkableFetcher
from src.fetcher.workday import WorkdayFetcher


class FetcherRegistry:
    """Selects and instantiates the appropriate fetcher based on the career page URL."""

    @classmethod
    def get_fetcher_for_url(
        cls,
        url: str,
        user_agent: str,
        timeout: int = 15,
        delay: float = 1.0,
        logger: Optional[logging.Logger] = None,
        use_tinyfish_fallback: bool = False,
    ) -> BaseFetcher:
        parsed = urlparse(url)
        domain = (parsed.netloc or "").lower()

        if use_tinyfish_fallback:
            return TinyFishFetcher(user_agent=user_agent, timeout=timeout, delay=delay, logger=logger)

        # 1. Amazon Jobs
        if "amazon.jobs" in domain:
            return AmazonFetcher(user_agent=user_agent, timeout=timeout, delay=delay, logger=logger)

        # 2. Workday
        if "myworkdayjobs.com" in domain:
            return WorkdayFetcher(user_agent=user_agent, timeout=timeout, delay=delay, logger=logger)

        # 3. Greenhouse
        if "greenhouse.io" in domain:
            return GreenhouseFetcher(user_agent=user_agent, timeout=timeout, delay=delay, logger=logger)

        # 4. Lever
        if "lever.co" in domain:
            return LeverFetcher(user_agent=user_agent, timeout=timeout, delay=delay, logger=logger)

        # 5. Ashby
        if "ashbyhq.com" in domain:
            return AshbyFetcher(user_agent=user_agent, timeout=timeout, delay=delay, logger=logger)

        # 6. SmartRecruiters
        if "smartrecruiters.com" in domain:
            return SmartRecruitersFetcher(user_agent=user_agent, timeout=timeout, delay=delay, logger=logger)

        # 7. Workable
        if "workable.com" in domain:
            return WorkableFetcher(user_agent=user_agent, timeout=timeout, delay=delay, logger=logger)

        # 8. Fallback: Generic parser with JSON-LD & HTML heuristics
        return GenericFetcher(user_agent=user_agent, timeout=timeout, delay=delay, logger=logger)
