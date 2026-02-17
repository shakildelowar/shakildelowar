"""Take screenshots of the portfolio report page using Playwright."""

import os
from datetime import datetime, timezone

from .config import load_config, list_urls


def get_screenshots_dir(config_path: str | None = None) -> str:
    config = load_config(config_path)
    d = config.get("screenshots_dir", "screenshots")
    if not os.path.isabs(d):
        base = os.path.dirname(os.path.abspath(config_path or "config.json"))
        d = os.path.join(base, d)
    os.makedirs(d, exist_ok=True)
    return d


def take_all_screenshots(config_path: str | None = None) -> list[dict]:
    """Screenshot the /report page which shows all wallet balances."""
    from playwright.sync_api import sync_playwright

    screenshots_dir = get_screenshots_dir(config_path)
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d_%H%M%S")
    filename = f"report_{date_str}.png"
    output_path = os.path.join(screenshots_dir, filename)

    port = int(os.environ.get("PORT", 5000))
    report_url = f"http://localhost:{port}/report"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
            )
            context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                java_script_enabled=True,
            )
            page = context.new_page()
            page.goto(report_url, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(2000)
            page.screenshot(path=output_path, full_page=True)
            browser.close()

        print(f"  OK: Portfolio report screenshot")
        return [{
            "url": "/report",
            "label": "Portfolio Report",
            "path": output_path,
            "filename": filename,
            "error": None,
        }]
    except Exception as e:
        print(f"  FAIL: Report screenshot - {e}")
        return [{
            "url": "/report",
            "label": "Portfolio Report",
            "path": None,
            "filename": None,
            "error": str(e),
        }]


def list_saved_screenshots(config_path: str | None = None) -> list[str]:
    """List all screenshot files sorted by name (newest last)."""
    d = get_screenshots_dir(config_path)
    files = [f for f in sorted(os.listdir(d)) if f.endswith(".png")]
    return files
