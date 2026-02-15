"""Load and manage URL + email configuration."""

import json
import os
from urllib.parse import urlparse

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")

ALLOWED_DOMAINS = ("debank.com", "jup.ag")


def _config_path(path: str | None) -> str:
    return os.path.abspath(path or DEFAULT_CONFIG_PATH)


def load_config(path: str | None = None) -> dict:
    config_path = _config_path(path)
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_path, "r") as f:
        return json.load(f)


def save_config(config: dict, path: str | None = None) -> None:
    config_path = _config_path(path)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")


def _validate_url(url: str) -> str:
    """Validate that the URL is a DeBank or Jupiter portfolio link."""
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url

    parsed = urlparse(url)
    host = parsed.hostname or ""

    if not any(host.endswith(d) for d in ALLOWED_DOMAINS):
        raise ValueError(
            f"URL must be from debank.com or jup.ag. Got: {host}"
        )
    return url


def add_url(url: str, label: str = "", path: str | None = None) -> str:
    """Add a URL to the config. Returns the cleaned URL."""
    url = _validate_url(url)
    config = load_config(path)

    for existing in config["urls"]:
        existing_url = existing if isinstance(existing, str) else existing.get("url", "")
        if existing_url.lower() == url.lower():
            raise ValueError(f"URL already exists: {url}")

    entry = {"url": url, "label": label or url}
    config["urls"].append(entry)
    save_config(config, path)
    return url


def remove_url(url: str, path: str | None = None) -> None:
    """Remove a URL from the config."""
    config = load_config(path)
    original_len = len(config["urls"])
    config["urls"] = [
        u for u in config["urls"]
        if (u if isinstance(u, str) else u.get("url", "")).lower() != url.lower()
    ]
    if len(config["urls"]) == original_len:
        raise ValueError(f"URL not found: {url}")
    save_config(config, path)


def list_urls(path: str | None = None) -> list[dict]:
    """List all configured URLs."""
    config = load_config(path)
    urls = []
    for entry in config.get("urls", []):
        if isinstance(entry, str):
            urls.append({"url": entry, "label": entry})
        else:
            urls.append(entry)
    return urls


def get_email_config(path: str | None = None) -> dict:
    config = load_config(path)
    return config.get("email", {})


def set_email_config(recipient: str, smtp_user: str, smtp_password: str,
                     smtp_host: str = "smtp.gmail.com", smtp_port: int = 587,
                     path: str | None = None) -> None:
    config = load_config(path)
    config["email"] = {
        "recipient": recipient,
        "smtp_host": smtp_host,
        "smtp_port": smtp_port,
        "smtp_user": smtp_user,
        "smtp_password": smtp_password,
    }
    save_config(config, path)
