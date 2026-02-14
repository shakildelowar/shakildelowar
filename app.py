#!/usr/bin/env python3
"""Flask web server for Portfolio Snapshots."""

import os

from flask import Flask, jsonify, render_template, request, send_from_directory

from src.config import add_url, get_email_config, list_urls, remove_url, set_email_config
from src.screenshots import get_screenshots_dir, list_saved_screenshots, take_all_screenshots
from src.emailer import send_screenshots_email

app = Flask(__name__)


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


# --- Screenshots ---

@app.route("/api/screenshots", methods=["GET"])
def get_screenshots():
    return jsonify(list_saved_screenshots())


@app.route("/api/screenshots/capture", methods=["POST"])
def capture_screenshots():
    results = take_all_screenshots()
    return jsonify({"ok": True, "results": results})


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
    # Mask the password for display
    masked = dict(cfg)
    if masked.get("smtp_password"):
        masked["smtp_password"] = masked["smtp_password"]
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
