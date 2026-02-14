"""Take screenshots of portfolio URLs using Playwright."""

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


def take_screenshot(url: str, output_path: str, wait_seconds: int = 8) -> str:
    """Take a full-page screenshot of a URL. Returns the output path."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(url, wait_until="networkidle", timeout=60000)
        # Extra wait for JS-heavy portfolio pages to finish rendering
        page.wait_for_timeout(wait_seconds * 1000)
        page.screenshot(path=output_path, full_page=True)
        browser.close()

    return output_path


def take_all_screenshots(config_path: str | None = None) -> list[dict]:
    """Screenshot every URL in config. Returns list of {url, label, path, error}."""
    urls = list_urls(config_path)
    screenshots_dir = get_screenshots_dir(config_path)

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d_%H%M%S")

    results = []
    for i, entry in enumerate(urls):
        url = entry["url"]
        label = entry.get("label", url)
        filename = f"shot_{i:02d}_{date_str}.png"
        output_path = os.path.join(screenshots_dir, filename)

        try:
            take_screenshot(url, output_path)
            results.append({
                "url": url,
                "label": label,
                "path": output_path,
                "filename": filename,
                "error": None,
            })
            print(f"  OK: {label}")
        except Exception as e:
            results.append({
                "url": url,
                "label": label,
                "path": None,
                "filename": None,
                "error": str(e),
            })
            print(f"  FAIL: {label} - {e}")

    return results


def list_saved_screenshots(config_path: str | None = None) -> list[str]:
    """List all screenshot files sorted by name (newest last)."""
    d = get_screenshots_dir(config_path)
    files = [f for f in sorted(os.listdir(d)) if f.endswith(".png")]
    return files
