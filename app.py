#!/usr/bin/env python3
"""Flask web server for Portfolio Snapshots."""

import os
import threading
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request, send_from_directory

from src.config import add_url, get_email_config, list_urls, remove_url, set_email_config
from src.screenshots import get_screenshots_dir, list_saved_screenshots, take_all_screenshots
from src.balances import fetch_all_balances, fetch_balance_for_url
from src.emailer import send_screenshots_email

app = Flask(__name__)


# --- Monthly scheduler (runs in background thread) ---

def _start_monthly_scheduler():
    """Start the end-of-month scheduler in a background daemon thread."""
    from src.scheduler import run_scheduler
    t = threading.Thread(target=run_scheduler, daemon=True)
    t.start()
    print("Monthly scheduler started in background thread.")


@app.route("/")
def index():
    return render_template("index.html")


# --- URL management ---

@app.route("/api/urls", methods=["GET"])
def get_urls():
    return jsonify(list_urls())


@app.route("/api/urls", methods=["POST"])
def post_url():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    url = data.get("url", "").strip()
    label = data.get("label", "").strip()
    if not url:
        return jsonify({"error": "URL is required"}), 400
    try:
        clean_url = add_url(url, label)
        return jsonify({"ok": True, "url": clean_url})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/urls", methods=["DELETE"])
def delete_url():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "URL is required"}), 400
    try:
        remove_url(url)
        return jsonify({"ok": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


# --- Balances ---

@app.route("/api/balances", methods=["GET"])
def get_balances():
    urls = list_urls()
    results = fetch_all_balances(urls)
    return jsonify(results)


@app.route("/report")
def balance_report():
    """Render a visual balance report page (also used for screenshots)."""
    urls = list_urls()
    wallets = fetch_all_balances(urls)
    now = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")
    return render_template("report.html", wallets=wallets, timestamp=now)


# --- Screenshots ---

@app.route("/api/screenshots", methods=["GET"])
def get_screenshots():
    return jsonify(list_saved_screenshots())


@app.route("/api/screenshots/capture", methods=["POST"])
def capture_screenshots():
    try:
        results = take_all_screenshots()
        return jsonify({"ok": True, "results": results})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc(), "results": []}), 500


@app.route("/api/screenshots/capture-and-email", methods=["POST"])
def capture_and_email():
    results = take_all_screenshots()
    successful = [r for r in results if r.get("path")]
    if not successful:
        return jsonify({"error": "No screenshots were captured"}), 500
    try:
        send_screenshots_email(results)
        return jsonify({
            "ok": True,
            "message": f"Emailed {len(successful)} screenshot(s)",
            "results": results,
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Email failed: {e}"}), 500


@app.route("/screenshots/<path:filename>")
def serve_screenshot(filename):
    screenshots_dir = get_screenshots_dir()
    return send_from_directory(screenshots_dir, filename)


# --- Email settings ---

@app.route("/api/email-settings", methods=["GET"])
def get_email_settings():
    cfg = get_email_config()
    masked = dict(cfg)
    return jsonify(masked)


@app.route("/api/email-settings", methods=["POST"])
def post_email_settings():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    try:
        set_email_config(
            recipient=data.get("recipient", ""),
            smtp_user=data.get("smtp_user", ""),
            smtp_password=data.get("smtp_password", ""),
            smtp_host=data.get("smtp_host", "smtp.gmail.com"),
            smtp_port=data.get("smtp_port", 587),
        )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/test-email", methods=["POST"])
def test_email():
    """Send a quick test email to verify SMTP settings."""
    import smtplib
    from email.mime.text import MIMEText

    cfg = get_email_config()
    recipient = cfg.get("recipient", "")
    smtp_user = cfg.get("smtp_user", "")
    smtp_password = cfg.get("smtp_password", "")
    smtp_host = cfg.get("smtp_host", "smtp.gmail.com")
    smtp_port = cfg.get("smtp_port", 587)

    if not recipient or not smtp_user or not smtp_password:
        return jsonify({"error": "Email settings incomplete. Fill in all fields first."}), 400

    try:
        msg = MIMEText("This is a test email from your Portfolio Tracker. If you see this, email is working!")
        msg["Subject"] = "Portfolio Tracker - Test Email"
        msg["From"] = smtp_user
        msg["To"] = recipient

        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)

        return jsonify({"ok": True, "message": f"Test email sent to {recipient}!"})
    except smtplib.SMTPAuthenticationError as e:
        return jsonify({"error": f"Authentication failed. Make sure you're using a Gmail App Password, not your regular password. ({e})"}), 400
    except Exception as e:
        return jsonify({"error": f"Email failed: {e}"}), 500


if __name__ == "__main__":
    _start_monthly_scheduler()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
