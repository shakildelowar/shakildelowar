#!/usr/bin/env python3
"""Portfolio Snapshots - Screenshot & email DeBank/Jupiter wallets monthly.

Usage:
    python main.py web                  # Start the web UI (default port 5000)
    python main.py capture              # Take screenshots of all URLs now
    python main.py email                # Capture screenshots and email them
    python main.py schedule             # Run end-of-month scheduler daemon
    python main.py list                 # List configured URLs
"""

import sys


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    command = sys.argv[1]

    if command == "web":
        from app import app
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
        app.run(host="0.0.0.0", port=port, debug=True)

    elif command == "capture":
        from src.screenshots import take_all_screenshots
        print("Taking screenshots...")
        results = take_all_screenshots()
        ok = sum(1 for r in results if not r.get("error"))
        fail = sum(1 for r in results if r.get("error"))
        print(f"\nDone: {ok} captured, {fail} failed")

    elif command == "email":
        from src.screenshots import take_all_screenshots
        from src.emailer import send_screenshots_email
        print("Taking screenshots...")
        results = take_all_screenshots()
        ok = [r for r in results if r.get("path")]
        if ok:
            print(f"Sending {len(ok)} screenshot(s) via email...")
            send_screenshots_email(results)
        else:
            print("No screenshots captured. Skipping email.")

    elif command == "schedule":
        from src.scheduler import run_scheduler
        run_scheduler()

    elif command == "list":
        from src.config import list_urls
        urls = list_urls()
        if not urls:
            print("No URLs configured.")
        else:
            for u in urls:
                label = u.get("label", "")
                print(f"  {label}")
                print(f"    {u['url']}")

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
