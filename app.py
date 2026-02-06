#!/usr/bin/env python3
"""Flask web server for the Portfolio Aggregator."""

from flask import Flask, jsonify, render_template, request

from src.aggregator import fetch_all_balances
from src.config import add_wallet, list_wallets, remove_wallet
from src.snapshot import list_snapshots, save_snapshot

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/wallets", methods=["GET"])
def get_wallets():
    return jsonify(list_wallets())


@app.route("/api/wallets", methods=["POST"])
def post_wallet():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    label = data.get("label", "").strip()
    address = data.get("address", "").strip()
    wallet_type = data.get("type", "").strip()

    if not address:
        return jsonify({"error": "Address is required"}), 400
    if wallet_type not in ("evm", "solana"):
        return jsonify({"error": "Type must be 'evm' or 'solana'"}), 400
    if not label:
        label = address[:12] + "..."

    try:
        add_wallet(label, address, wallet_type)
        return jsonify({"ok": True, "label": label, "address": address, "type": wallet_type})
    except ValueError as e:
        return jsonify({"error": str(e)}), 409


@app.route("/api/wallets", methods=["DELETE"])
def delete_wallet():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    address = data.get("address", "").strip()
    if not address:
        return jsonify({"error": "Address is required"}), 400

    try:
        remove_wallet(address)
        return jsonify({"ok": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@app.route("/api/balances", methods=["GET"])
def get_balances():
    data = fetch_all_balances()
    return jsonify(data)


@app.route("/api/snapshot", methods=["POST"])
def post_snapshot():
    data = fetch_all_balances()
    filepath = save_snapshot(data)
    filename = filepath.rsplit("/", 1)[-1]
    return jsonify({"ok": True, "file": filename, "data": data})


@app.route("/api/snapshots", methods=["GET"])
def get_snapshots():
    return jsonify(list_snapshots())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
