#!/usr/bin/env python3
"""Job Search Monitor CLI Entrypoint.

Usage:
    python main.py --once
    python main.py --schedule
    python main.py --init-template
    python main.py --config config.yaml
    python main.py --workbook my_jobs.xlsx
"""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

from src.config import AppConfig
from src.excel_handler import ExcelHandler
from src.fetcher.registry import FetcherRegistry
from src.logger import setup_logger
from src.matcher import JobMatcher
from src.models import JobSource
from src.monitor import JobMonitor


def parse_args():
    parser = argparse.ArgumentParser(
        description="Daily Python Job-Search Monitor with Excel Sources and Matches."
    )
    parser.add_argument(
        "--once",
        action="store_true",
        default=True,
        help="Run the monitor immediately once and exit (default behavior).",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run continuously and trigger daily at the scheduled time in config.yaml.",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to YAML configuration file (default: config.yaml).",
    )
    parser.add_argument(
        "--workbook",
        type=str,
        default=None,
        help="Path to the Excel workbook (overrides config.yaml).",
    )
    parser.add_argument(
        "--init-template",
        action="store_true",
        help="Create a template Excel workbook if it doesn't exist, and exit.",
    )
    parser.add_argument(
        "--update-watchlist",
        action="store_true",
        help="Update or populate the Sources sheet with the full India watchlist.",
    )
    parser.add_argument(
        "--clean-demo",
        action="store_true",
        help="Clean only demo / example rows from the Matches sheet.",
    )
    parser.add_argument(
        "--test-source",
        type=str,
        default=None,
        help="Test fetching and matching for a single career URL without modifying the workbook.",
    )
    return parser.parse_args()


def run_scheduler(monitor: JobMonitor, target_time_str: str):
    """Run continuously, executing monitor.run() once a day at target_time_str (HH:MM)."""
    logger = monitor.logger
    logger.info(f"Scheduler mode active. Monitoring will run daily at {target_time_str}.")
    logger.info("Press Ctrl+C to terminate.")

    last_run_date = None

    while True:
        now = datetime.now()
        current_time_str = now.strftime("%H:%M")
        today_date = now.date()

        if current_time_str == target_time_str and last_run_date != today_date:
            logger.info(f"Scheduled trigger reached ({target_time_str}). Executing daily run...")
            try:
                monitor.run()
            except Exception as e:
                logger.error(f"Scheduled run failed with error: {e}")
            last_run_date = today_date

        # Sleep for 30 seconds before checking time again
        time.sleep(30)


def test_single_source(url: str, config: AppConfig):
    """Test fetching from a single URL without writing to the workbook."""
    logger = setup_logger(log_dir=config.log_dir, log_level=config.log_level)
    logger.info(f"Testing single URL: {url}")
    
    source = JobSource(
        company_name="Test Company",
        careers_url=url,
        active=True,
    )
    fetcher = FetcherRegistry.get_fetcher_for_url(
        url=url,
        user_agent=config.user_agent,
        timeout=config.request_timeout,
        delay=config.rate_limit_delay,
        logger=logger,
    )
    try:
        listings = fetcher.fetch_jobs(source)
        logger.info(f"Retrieved {len(listings)} listings.")
        for idx, job in enumerate(listings[:10], 1):
            print(f"{idx}. {job.title} | {job.location} | {job.url} (Posted: {job.posted_date})")
        if len(listings) > 10:
            print(f"... and {len(listings) - 10} more listings.")
    except Exception as e:
        logger.error(f"Test failed: {e}")


def main():
    args = parse_args()

    # Load configuration
    config = AppConfig.from_file(args.config)
    if args.workbook:
        config.workbook_path = args.workbook

    if args.init_template:
        print(f"Creating template Excel workbook at '{config.workbook_path}'...")
        handler = ExcelHandler(config.workbook_path)
        handler.create_template_workbook()
        print("Template created successfully with Sources and Matches sheets.")
        sys.exit(0)

    if args.clean_demo:
        print(f"Cleaning demo listings from '{config.workbook_path}'...")
        handler = ExcelHandler(config.workbook_path)
        handler.clean_demo_data()
        print("Demo listings cleaned. Real matches and user notes preserved.")
        sys.exit(0)

    if args.update_watchlist:
        print(f"Updating watchlist in '{config.workbook_path}'...")
        handler = ExcelHandler(config.workbook_path)
        handler.populate_watchlist()
        print("Watchlist updated successfully.")
        sys.exit(0)

    if args.test_source:
        test_single_source(args.test_source, config)
        sys.exit(0)

    monitor = JobMonitor(config)

    if args.schedule:
        run_scheduler(monitor, config.schedule_time)
    else:
        # One-off execution
        monitor.run()


if __name__ == "__main__":
    main()

