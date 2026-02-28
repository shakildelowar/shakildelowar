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


def _clear_old_screenshots(screenshots_dir: str) -> None:
    for f in os.listdir(screenshots_dir):
        if f.endswith(".png"):
            try:
                os.remove(os.path.join(screenshots_dir, f))
            except OSError:
                pass


def take_screenshot(url: str, output_path: str) -> str:
    """Take a screenshot of a URL, handling Cloudflare challenges."""
    from playwright.sync_api import sync_playwright

    try:
        from playwright_stealth import stealth_sync
        has_stealth = True
    except ImportError:
        has_stealth = False
        print("[Screenshots] playwright-stealth not installed, using basic mode")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            java_script_enabled=True,
            locale="en-US",
            timezone_id="America/New_York",
            color_scheme="dark",
        )
        page = context.new_page()

        if has_stealth:
            stealth_sync(page)

        print(f"[Screenshots] Loading {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)

        # Wait for Cloudflare challenge to auto-resolve (up to 20s)
        for i in range(20):
            title = page.title().lower()
            if "just a moment" not in title and "attention" not in title:
                break
            if i == 0:
                print("[Screenshots] Cloudflare challenge detected, waiting...")
            page.wait_for_timeout(1000)

        # Wait for real page to finish loading
        try:
            page.wait_for_load_state("networkidle", timeout=30000)
        except Exception:
            pass

        # Let JS render
        page.wait_for_timeout(5000)

        page.screenshot(path=output_path, full_page=True)
        print(f"[Screenshots] Saved {output_path}")
        browser.close()

    return output_path


def take_all_screenshots(config_path: str | None = None) -> list[dict]:
    """Screenshot every URL in config."""
    urls = list_urls(config_path)
    if not urls:
        return []

    screenshots_dir = get_screenshots_dir(config_path)
    _clear_old_screenshots(screenshots_dir)

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
    d = get_screenshots_dir(config_path)
    files = [f for f in sorted(os.listdir(d)) if f.endswith(".png")]
    return files
