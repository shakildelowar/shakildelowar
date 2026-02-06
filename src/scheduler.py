"""Schedule monthly snapshots at UTC month-end."""

import calendar
import time
from datetime import datetime, timezone

from .aggregator import fetch_all_balances, format_report
from .snapshot import save_snapshot


def is_last_day_of_month(dt: datetime) -> bool:
    """Check if the given date is the last day of its month."""
    last_day = calendar.monthrange(dt.year, dt.month)[1]
    return dt.day == last_day


def run_snapshot(config_path: str | None = None) -> str:
    """Run a snapshot now and save it. Returns filepath."""
    print("Fetching balances from all wallets...")
    data = fetch_all_balances(config_path)
    report = format_report(data)
    print(report)

    filepath = save_snapshot(data, config_path)
    print(f"\nSnapshot saved to: {filepath}")
    return filepath


def run_scheduler(config_path: str | None = None) -> None:
    """Run continuously, taking a snapshot at 23:59 UTC on the last day of each month."""
    print("Monthly snapshot scheduler started.")
    print("Will take snapshots at ~23:59 UTC on the last day of each month.")
    print("Press Ctrl+C to stop.\n")

    last_snapshot_month = None

    while True:
        now = datetime.now(timezone.utc)

        # Check if it's the last day of the month, after 23:50 UTC
        if (
            is_last_day_of_month(now)
            and now.hour == 23
            and now.minute >= 50
            and last_snapshot_month != (now.year, now.month)
        ):
            print(f"\n[{now.isoformat()}] End of month detected. Taking snapshot...")
            try:
                run_snapshot(config_path)
                last_snapshot_month = (now.year, now.month)
                print(f"Next snapshot: end of next month\n")
            except Exception as e:
                print(f"Error taking snapshot: {e}")

        # Sleep for 60 seconds before checking again
        time.sleep(60)
