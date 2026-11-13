"""Configuration loader for the job search monitor."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict
import yaml


@dataclass
class AppConfig:
    workbook_path: str = "job_search.xlsx"
    schedule_time: str = "09:00"  # 24-hour HH:MM format
    request_timeout: int = 15     # Seconds
    rate_limit_delay: float = 1.0 # Seconds between requests
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (JobSearchMonitor/1.0; Public Careers Checker)"
    log_level: str = "INFO"
    log_dir: str = "logs"
    save_daily_summary_log: bool = True

    @classmethod
    def from_file(cls, config_path: str | Path = "config.yaml") -> "AppConfig":
        path = Path(config_path)
        if not path.is_file():
            return cls()

        try:
            with open(path, "r", encoding="utf-8") as f:
                data: Dict[str, Any] = yaml.safe_load(f) or {}
        except Exception:
            return cls()

        return cls(
            workbook_path=str(data.get("workbook_path", "job_search.xlsx")),
            schedule_time=str(data.get("schedule_time", "09:00")),
            request_timeout=int(data.get("request_timeout", 15)),
            rate_limit_delay=float(data.get("rate_limit_delay", 1.0)),
            user_agent=str(data.get("user_agent", "JobSearchMonitor/1.0 (Public Careers Checker)")),
            log_level=str(data.get("log_level", "INFO")),
            log_dir=str(data.get("log_dir", "logs")),
            save_daily_summary_log=bool(data.get("save_daily_summary_log", True)),
        )

