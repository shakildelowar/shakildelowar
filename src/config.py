"""Load and manage wallet configuration."""

import json
import os

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")


def load_config(path: str | None = None) -> dict:
    """Load configuration from JSON file."""
    config_path = path or DEFAULT_CONFIG_PATH
    config_path = os.path.abspath(config_path)

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r") as f:
        return json.load(f)


def save_config(config: dict, path: str | None = None) -> None:
    """Save configuration to JSON file."""
    config_path = path or DEFAULT_CONFIG_PATH
    config_path = os.path.abspath(config_path)

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")


def add_wallet(label: str, address: str, wallet_type: str, path: str | None = None) -> None:
    """Add a new wallet to the config."""
    if wallet_type not in ("evm", "solana"):
        raise ValueError(f"Invalid wallet type: {wallet_type}. Must be 'evm' or 'solana'.")

    config = load_config(path)
    # Check for duplicate address
    for w in config["wallets"]:
        if w["address"].lower() == address.lower():
            raise ValueError(f"Wallet {address} already exists in config.")

    config["wallets"].append({
        "label": label,
        "address": address,
        "type": wallet_type,
    })
    save_config(config, path)


def remove_wallet(address: str, path: str | None = None) -> None:
    """Remove a wallet from the config by address."""
    config = load_config(path)
    original_len = len(config["wallets"])
    config["wallets"] = [
        w for w in config["wallets"]
        if w["address"].lower() != address.lower()
    ]
    if len(config["wallets"]) == original_len:
        raise ValueError(f"Wallet {address} not found in config.")
    save_config(config, path)


def list_wallets(path: str | None = None) -> list[dict]:
    """List all configured wallets."""
    config = load_config(path)
    return config.get("wallets", [])
