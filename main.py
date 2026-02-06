#!/usr/bin/env python3
"""Monthly Portfolio Balance Aggregator.

Tracks wallet balances across DeBank (EVM) and Jupiter (Solana),
takes monthly snapshots, and reports aggregated portfolio value.

Usage:
    python main.py snapshot              # Take a snapshot now
    python main.py balances              # Show current balances (no save)
    python main.py history               # Show saved snapshots
    python main.py monthly               # Show monthly summary
    python main.py add <label> <address> <evm|solana>   # Add a wallet
    python main.py remove <address>      # Remove a wallet
    python main.py list                  # List configured wallets
    python main.py schedule              # Run monthly scheduler daemon
"""

import sys

from src.aggregator import fetch_all_balances, format_report
from src.config import add_wallet, list_wallets, remove_wallet
from src.scheduler import run_scheduler, run_snapshot
from src.snapshot import get_monthly_summary, list_snapshots


def cmd_snapshot(config_path: str | None = None) -> None:
    """Take a snapshot and save it."""
    run_snapshot(config_path)


def cmd_balances(config_path: str | None = None) -> None:
    """Show current balances without saving."""
    data = fetch_all_balances(config_path)
    print(format_report(data))


def cmd_history(config_path: str | None = None) -> None:
    """Show all saved snapshots."""
    snapshots = list_snapshots(config_path)
    if not snapshots:
        print("No snapshots found.")
        return

    print(f"{'Date':<25} {'Total USD':>15} {'Wallets':>10}")
    print("-" * 52)
    for snap in snapshots:
        print(f"{snap['timestamp']:<25} ${snap['total_usd']:>13,.2f} {snap['wallet_count']:>10}")


def cmd_monthly(config_path: str | None = None) -> None:
    """Show monthly summary."""
    summary = get_monthly_summary(config_path)
    if not summary:
        print("No monthly data found.")
        return

    print(f"{'Month':<12} {'Snapshots':>10} {'Last Balance':>15}")
    print("-" * 40)
    for entry in summary:
        print(f"{entry['month']:<12} {entry['snapshot_count']:>10} ${entry['last_total_usd']:>13,.2f}")


def cmd_add(args: list[str], config_path: str | None = None) -> None:
    """Add a wallet."""
    if len(args) < 3:
        print("Usage: python main.py add <label> <address> <evm|solana>")
        sys.exit(1)

    label, address, wallet_type = args[0], args[1], args[2]
    try:
        add_wallet(label, address, wallet_type, config_path)
        print(f"Added {wallet_type} wallet '{label}': {address}")
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_remove(args: list[str], config_path: str | None = None) -> None:
    """Remove a wallet."""
    if len(args) < 1:
        print("Usage: python main.py remove <address>")
        sys.exit(1)

    address = args[0]
    try:
        remove_wallet(address, config_path)
        print(f"Removed wallet: {address}")
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_list(config_path: str | None = None) -> None:
    """List all configured wallets."""
    wallets = list_wallets(config_path)
    if not wallets:
        print("No wallets configured. Use 'add' to add one.")
        return

    print(f"{'Label':<25} {'Type':<8} {'Address'}")
    print("-" * 80)
    for w in wallets:
        print(f"{w.get('label', 'N/A'):<25} {w['type']:<8} {w['address']}")


def cmd_schedule(config_path: str | None = None) -> None:
    """Run the monthly scheduler."""
    run_scheduler(config_path)


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    command = sys.argv[1]
    config_path = None

    # Check for --config flag
    for i, arg in enumerate(sys.argv):
        if arg == "--config" and i + 1 < len(sys.argv):
            config_path = sys.argv[i + 1]

    commands = {
        "snapshot": lambda: cmd_snapshot(config_path),
        "balances": lambda: cmd_balances(config_path),
        "history": lambda: cmd_history(config_path),
        "monthly": lambda: cmd_monthly(config_path),
        "add": lambda: cmd_add(sys.argv[2:], config_path),
        "remove": lambda: cmd_remove(sys.argv[2:], config_path),
        "list": lambda: cmd_list(config_path),
        "schedule": lambda: cmd_schedule(config_path),
    }

    if command in commands:
        commands[command]()
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
