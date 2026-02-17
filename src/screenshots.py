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

        # Wait for loading spinners to disappear
        # Jupiter uses a spinner, DeBank uses loading indicators
        for selector in [
            # Common loading indicators
            "[class*='spinner']",
            "[class*='loading']",
            "[class*='skeleton']",
        ]:
            try:
                page.wait_for_selector(selector, state="hidden", timeout=15000)
            except Exception:
                pass

        # Dismiss cookie banners and popups
        for dismiss_selector in [
            # Zerion cookie banner "Accept" button
            "button:has-text('Accept')",
            "button:has-text('Accept All')",
            "button:has-text('Got it')",
            "button:has-text('I agree')",
            # Generic cookie consent
            "[class*='cookie'] button",
            "[id*='cookie'] button",
            "[class*='consent'] button",
        ]:
            try:
                btn = page.locator(dismiss_selector).first
                if btn.is_visible(timeout=1000):
                    btn.click()
                    page.wait_for_timeout(500)
                    break
            except Exception:
                pass

        # Hide distracting overlays (Zerion sidebar, premium banners)
        page.evaluate("""
            // Remove fixed/sticky elements that overlay content
            document.querySelectorAll('[class*="cookie"], [class*="consent"], [class*="banner"]').forEach(el => {
                if (el.style) el.style.display = 'none';
            });
            // Hide Zerion left sidebar and premium promo for cleaner screenshot
            document.querySelectorAll('nav, [class*="sidebar"], [class*="premium"], [class*="Premium"]').forEach(el => {
                if (el.style) el.style.display = 'none';
            });
        """)

        # Final wait for any last renders
        page.wait_for_timeout(3000)

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
