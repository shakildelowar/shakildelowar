"""Aggregate balances from all configured wallets."""

from datetime import datetime, timezone

from .config import load_config
from .fetchers import fetch_debank_balance, fetch_jupiter_balance


def fetch_all_balances(config_path: str | None = None) -> dict:
    """Fetch balances for all wallets in config and aggregate."""
    config = load_config(config_path)
    wallets = config.get("wallets", [])

    results = []
    total_usd = 0.0
    errors = []

    for wallet in wallets:
        address = wallet["address"]
        label = wallet.get("label", address)
        wallet_type = wallet["type"]

        if wallet_type == "evm":
            result = fetch_debank_balance(address)
        elif wallet_type == "solana":
            result = fetch_jupiter_balance(address)
        else:
            result = {
                "address": address,
                "source": "unknown",
                "usd_value": None,
                "error": f"Unknown wallet type: {wallet_type}",
            }

        result["label"] = label
        results.append(result)

        if result.get("error"):
            errors.append(f"{label} ({address}): {result['error']}")
        elif result.get("usd_value") is not None:
            total_usd += result["usd_value"]

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "wallets": results,
        "total_usd": total_usd,
        "errors": errors,
        "wallet_count": len(wallets),
    }


def format_report(data: dict) -> str:
    """Format aggregated data into a readable report."""
    lines = []
    lines.append("=" * 60)
    lines.append("  PORTFOLIO BALANCE SNAPSHOT")
    lines.append(f"  {data['timestamp']}")
    lines.append("=" * 60)
    lines.append("")

    for wallet in data["wallets"]:
        label = wallet.get("label", wallet["address"])
        source = wallet.get("source", "unknown")
        url = wallet.get("url", "")

        if wallet.get("error"):
            lines.append(f"  [{source.upper()}] {label}")
            lines.append(f"    Address: {wallet['address']}")
            lines.append(f"    ERROR: {wallet['error']}")
        else:
            usd = wallet.get("usd_value", 0)
            lines.append(f"  [{source.upper()}] {label}")
            lines.append(f"    Address: {wallet['address']}")
            lines.append(f"    Balance: ${usd:,.2f}")
            lines.append(f"    URL: {url}")

            # Extra detail for Solana wallets
            if source == "jupiter" and wallet.get("sol_balance") is not None:
                lines.append(f"    SOL: {wallet['sol_balance']:.4f} (${wallet.get('sol_usd', 0):,.2f})")
                token_count = len(wallet.get("token_balances", {}))
                if token_count:
                    lines.append(f"    SPL Tokens: {token_count}")

        lines.append("")

    lines.append("-" * 60)
    lines.append(f"  TOTAL PORTFOLIO VALUE: ${data['total_usd']:,.2f}")
    lines.append(f"  Wallets: {data['wallet_count']}")
    if data.get("errors"):
        lines.append(f"  Errors: {len(data['errors'])}")
    lines.append("-" * 60)

    return "\n".join(lines)
