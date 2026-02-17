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


def _is_cloudflare_blocked(page) -> bool:
    """Check if the page is showing a Cloudflare challenge."""
    try:
        title = page.title().lower()
        if "just a moment" in title or "attention required" in title:
            return True
        # Check for Cloudflare challenge elements
        cf = page.locator("text=Verify you are human").count()
        if cf > 0:
            return True
        cf2 = page.locator("text=Performing security verification").count()
        if cf2 > 0:
            return True
    except Exception:
        pass
    return False


def take_screenshot(url: str, output_path: str) -> str:
    """Take a full-page screenshot of a URL. Returns the output path."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        # Use a real browser context to avoid bot detection
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
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            java_script_enabled=True,
            locale="en-US",
        )
        page = context.new_page()

        # Hide webdriver flag from detection scripts
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
        """)

        page.goto(url, wait_until="domcontentloaded", timeout=60000)

        # Wait for network to settle (API calls fetching wallet data)
        try:
            page.wait_for_load_state("networkidle", timeout=30000)
        except Exception:
            pass

        # Check if blocked by Cloudflare
        blocked = _is_cloudflare_blocked(page)
        if blocked:
            browser.close()
            raise CloudflareBlockedError(f"Cloudflare blocked: {url}")

        # Wait for loading spinners to disappear
        for selector in [
            "[class*='spinner']",
            "[class*='loading']",
            "[class*='skeleton']",
        ]:
            try:
                page.wait_for_selector(selector, state="hidden", timeout=15000)
            except Exception:
                pass

        # Final wait for any last renders
        page.wait_for_timeout(5000)

        page.screenshot(path=output_path, full_page=True)
        browser.close()

    return output_path


def _take_report_screenshot(output_path: str) -> str:
    """Screenshot our own /report page as fallback (no Cloudflare issues)."""
    from playwright.sync_api import sync_playwright

    port = int(os.environ.get("PORT", 5000))
    report_url = f"http://localhost:{port}/report"

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
        page.goto(report_url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)
        page.screenshot(path=output_path, full_page=True)
        browser.close()

    return output_path


class CloudflareBlockedError(Exception):
    pass


def take_all_screenshots(config_path: str | None = None) -> list[dict]:
    """Screenshot every URL in config. Falls back to /report if Cloudflare blocks."""
    urls = list_urls(config_path)
    screenshots_dir = get_screenshots_dir(config_path)

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d_%H%M%S")

    results = []
    used_report_fallback = False

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
        except CloudflareBlockedError:
            print(f"  BLOCKED: {label} - Cloudflare detected, will use report fallback")
            used_report_fallback = True
            results.append({
                "url": url,
                "label": label,
                "path": None,
                "filename": None,
                "error": "Cloudflare blocked - see report screenshot",
            })
        except Exception as e:
            results.append({
                "url": url,
                "label": label,
                "path": None,
                "filename": None,
                "error": str(e),
            })
            print(f"  FAIL: {label} - {e}")

    # If any URL was blocked by Cloudflare, take a report screenshot as fallback
    if used_report_fallback:
        report_filename = f"report_{date_str}.png"
        report_path = os.path.join(screenshots_dir, report_filename)
        try:
            _take_report_screenshot(report_path)
            results.append({
                "url": "/report",
                "label": "Portfolio Report (fallback)",
                "path": report_path,
                "filename": report_filename,
                "error": None,
            })
            print("  OK: Report fallback screenshot")
        except Exception as e:
            print(f"  FAIL: Report fallback - {e}")

    return results


def list_saved_screenshots(config_path: str | None = None) -> list[str]:
    """List all screenshot files sorted by name (newest last)."""
    d = get_screenshots_dir(config_path)
    files = [f for f in sorted(os.listdir(d)) if f.endswith(".png")]
    return files
