"""Manage monthly snapshots of portfolio balances."""

import json
import os
from datetime import datetime, timezone

from .config import load_config


def get_snapshot_dir(config_path: str | None = None) -> str:
    """Get the snapshot directory from config."""
    config = load_config(config_path)
    snapshot_dir = config.get("snapshot_dir", "snapshots")
    if not os.path.isabs(snapshot_dir):
        base = os.path.dirname(os.path.abspath(config_path or "config.json"))
        snapshot_dir = os.path.join(base, snapshot_dir)
    os.makedirs(snapshot_dir, exist_ok=True)
    return snapshot_dir


def save_snapshot(data: dict, config_path: str | None = None) -> str:
    """Save a balance snapshot to a JSON file.

    Returns the file path of the saved snapshot.
    """
    snapshot_dir = get_snapshot_dir(config_path)
    timestamp = data.get("timestamp", datetime.now(timezone.utc).isoformat())

    # Parse the timestamp to create a filename
    try:
        dt = datetime.fromisoformat(timestamp)
    except (ValueError, TypeError):
        dt = datetime.now(timezone.utc)

    filename = f"snapshot_{dt.strftime('%Y-%m-%d_%H%M%S')}.json"
    filepath = os.path.join(snapshot_dir, filename)

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, default=str)
        f.write("\n")

    return filepath


def load_snapshot(filepath: str) -> dict:
    """Load a snapshot from a JSON file."""
    with open(filepath, "r") as f:
        return json.load(f)


def list_snapshots(config_path: str | None = None) -> list[dict]:
    """List all saved snapshots with summary info."""
    snapshot_dir = get_snapshot_dir(config_path)
    snapshots = []

    for filename in sorted(os.listdir(snapshot_dir)):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(snapshot_dir, filename)
        try:
            data = load_snapshot(filepath)
            snapshots.append({
                "file": filename,
                "path": filepath,
                "timestamp": data.get("timestamp", "unknown"),
                "total_usd": data.get("total_usd", 0),
                "wallet_count": data.get("wallet_count", 0),
            })
        except (json.JSONDecodeError, KeyError):
            continue

    return snapshots


def get_monthly_summary(config_path: str | None = None) -> list[dict]:
    """Get a summary of snapshots grouped by month."""
    snapshots = list_snapshots(config_path)
    monthly = {}

    for snap in snapshots:
        try:
            dt = datetime.fromisoformat(snap["timestamp"])
            month_key = dt.strftime("%Y-%m")
        except (ValueError, TypeError):
            continue

        if month_key not in monthly:
            monthly[month_key] = []
        monthly[month_key].append(snap)

    # For each month, get the last snapshot (closest to end of month)
    summary = []
    for month, snaps in sorted(monthly.items()):
        last_snap = snaps[-1]  # already sorted by filename/date
        summary.append({
            "month": month,
            "snapshot_count": len(snaps),
            "last_total_usd": last_snap["total_usd"],
            "last_timestamp": last_snap["timestamp"],
        })

    return summary
