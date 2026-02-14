"""End-of-month scheduler: screenshots + email."""

import calendar
import time
from datetime import datetime, timezone

from .screenshots import take_all_screenshots
from .emailer import send_screenshots_email


def is_last_day_of_month(dt: datetime) -> bool:
    last_day = calendar.monthrange(dt.year, dt.month)[1]
    return dt.day == last_day


def run_monthly_job(config_path: str | None = None) -> None:
    """Take all screenshots and email them."""
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting monthly snapshot...")
    print("Taking screenshots...")
    results = take_all_screenshots(config_path)

    successful = [r for r in results if r.get("path")]
    if not successful:
        print("No screenshots were captured. Skipping email.")
        return

    print(f"\nSending email with {len(successful)} screenshot(s)...")
    try:
        send_screenshots_email(results, config_path)
        print("Done.")
    except Exception as e:
        print(f"Email failed: {e}")


def run_scheduler(config_path: str | None = None) -> None:
    """Run continuously. Screenshots + email at ~23:50 UTC on last day of month."""
    print("Monthly screenshot scheduler started.")
    print("Will capture and email at ~23:50 UTC on the last day of each month.")
    print("Press Ctrl+C to stop.\n")

    last_run_month = None

    while True:
        now = datetime.now(timezone.utc)

        if (
            is_last_day_of_month(now)
            and now.hour == 23
            and now.minute >= 50
            and last_run_month != (now.year, now.month)
        ):
            try:
                run_monthly_job(config_path)
                last_run_month = (now.year, now.month)
                print(f"Next run: end of next month\n")
            except Exception as e:
                print(f"Error: {e}")

        time.sleep(60)
