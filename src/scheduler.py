"""Monthly scheduler: screenshots + balance report email on the 29th at 5 UTC."""

import time
from datetime import datetime, timezone

from .screenshots import take_all_screenshots
from .emailer import send_screenshots_email


REPORT_DAY = 29
REPORT_HOUR = 5


def run_monthly_job(config_path: str | None = None) -> None:
    """Take all screenshots and email them with balance report."""
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting monthly snapshot...")
    print("Taking screenshots...")
    results = take_all_screenshots(config_path)

    successful = [r for r in results if r.get("path")]
    print(f"Screenshots captured: {len(successful)}/{len(results)}")

    print("Sending email with screenshots + balance report...")
    try:
        send_screenshots_email(results, config_path, include_balances=True)
        print("Done.")
    except Exception as e:
        print(f"Email failed: {e}")


def run_scheduler(config_path: str | None = None) -> None:
    """Run continuously. Screenshots + email at 5:00 UTC on the 29th of each month."""
    print("Monthly screenshot scheduler started.")
    print(f"Will capture and email at {REPORT_HOUR:02d}:00 UTC on the 29th of each month.")
    print("Press Ctrl+C to stop.\n")

    last_run_month = None

    while True:
        now = datetime.now(timezone.utc)

        if (
            now.day == REPORT_DAY
            and now.hour == REPORT_HOUR
            and now.minute < 10
            and last_run_month != (now.year, now.month)
        ):
            try:
                run_monthly_job(config_path)
                last_run_month = (now.year, now.month)
                print(f"Next run: 29th of next month at {REPORT_HOUR:02d}:00 UTC\n")
            except Exception as e:
                print(f"Error: {e}")

        time.sleep(60)
