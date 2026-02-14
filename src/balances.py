"""Fetch wallet balances from Solana RPC and DeBank API."""

import requests
from urllib.parse import urlparse

SOLANA_RPC = "https://api.mainnet-beta.solana.com"
JUPITER_PRICE_API = "https://api.jup.ag/price/v2"
SOL_MINT = "So11111111111111111111111111111111111111112"
LAMPORTS_PER_SOL = 1_000_000_000

DEBANK_API = "https://api.debank.com/user/total_balance"


def extract_address_from_url(url: str) -> tuple[str, str]:
    """Extract wallet address and type from a DeBank/Jupiter URL.

    Returns (address, type) where type is 'solana' or 'evm'.
    """
    parsed = urlparse(url)
    host = parsed.hostname or ""
    path = parsed.path.rstrip("/")

    if "jup.ag" in host:
        # https://jup.ag/portfolio/<address>
        parts = path.split("/")
        address = parts[-1] if len(parts) >= 2 else ""
        return address, "solana"
    elif "debank.com" in host:
        # https://debank.com/profile/<address>
        parts = path.split("/")
        address = parts[-1] if len(parts) >= 2 else ""
        return address, "evm"

    return "", "unknown"


def _sol_balance(address: str) -> float | None:
    try:
        resp = requests.post(SOLANA_RPC, json={
            "jsonrpc": "2.0", "id": 1,
            "method": "getBalance",
            "params": [address],
        }, timeout=15)
        resp.raise_for_status()
        lamports = resp.json().get("result", {}).get("value", 0)
        return lamports / LAMPORTS_PER_SOL
    except Exception:
        return None


def _spl_tokens(address: str) -> list[dict]:
    try:
        resp = requests.post(SOLANA_RPC, json={
            "jsonrpc": "2.0", "id": 1,
            "method": "getTokenAccountsByOwner",
            "params": [
                address,
                {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                {"encoding": "jsonParsed"},
            ],
        }, timeout=15)
        resp.raise_for_status()
        accounts = resp.json().get("result", {}).get("value", [])
        tokens = []
        for acct in accounts:
            info = acct["account"]["data"]["parsed"]["info"]
            mint = info.get("mint", "")
            ui_amount = info.get("tokenAmount", {}).get("uiAmount", 0)
            decimals = info.get("tokenAmount", {}).get("decimals", 0)
            if ui_amount and ui_amount > 0:
                tokens.append({"mint": mint, "amount": ui_amount, "decimals": decimals})
        return tokens
    except Exception:
        return []


def _token_prices(mints: list[str]) -> dict[str, float]:
    if not mints:
        return {}
    try:
        resp = requests.get(JUPITER_PRICE_API, params={"ids": ",".join(mints)}, timeout=15)
        resp.raise_for_status()
        data = resp.json().get("data", {})
        return {m: float(info["price"]) for m, info in data.items() if info.get("price")}
    except Exception:
        return {}


def _token_metadata(mints: list[str]) -> dict[str, dict]:
    """Try to get token names/symbols from Jupiter token list."""
    meta = {}
    try:
        resp = requests.get("https://tokens.jup.ag/tokens?tags=verified", timeout=10)
        resp.raise_for_status()
        for token in resp.json():
            if token.get("address") in mints:
                meta[token["address"]] = {
                    "symbol": token.get("symbol", "???"),
                    "name": token.get("name", "Unknown"),
                }
    except Exception:
        pass
    return meta


def fetch_solana_balance(address: str) -> dict:
    """Fetch full Solana wallet balance."""
    sol = _sol_balance(address)
    tokens = _spl_tokens(address)

    all_mints = [SOL_MINT] + [t["mint"] for t in tokens]
    prices = _token_prices(all_mints)
    metadata = _token_metadata(all_mints)

    sol_price = prices.get(SOL_MINT, 0)
    sol_usd = (sol or 0) * sol_price

    token_list = []
    total_tokens_usd = 0.0

    for t in tokens:
        price = prices.get(t["mint"], 0)
        usd = t["amount"] * price
        if usd < 0.01:
            continue
        meta = metadata.get(t["mint"], {})
        token_list.append({
            "mint": t["mint"],
            "symbol": meta.get("symbol", t["mint"][:6] + "..."),
            "name": meta.get("name", "Unknown"),
            "amount": t["amount"],
            "price": price,
            "usd": usd,
        })
        total_tokens_usd += usd

    # Sort by USD value descending
    token_list.sort(key=lambda x: x["usd"], reverse=True)

    return {
        "address": address,
        "type": "solana",
        "sol_balance": sol,
        "sol_price": sol_price,
        "sol_usd": sol_usd,
        "tokens": token_list,
        "total_usd": sol_usd + total_tokens_usd,
        "error": None,
    }


def fetch_evm_balance(address: str) -> dict:
    """Fetch EVM wallet balance from DeBank."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": f"https://debank.com/profile/{address}",
    }
    try:
        resp = requests.get(
            DEBANK_API,
            params={"addr": address.lower()},
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})

        total = data.get("total_usd_value", 0.0)
        chains = []
        for chain in data.get("chain_list", []):
            usd = chain.get("usd_value", 0)
            if usd > 0.01:
                chains.append({
                    "id": chain.get("community_id") or chain.get("id", "?"),
                    "name": chain.get("name", "Unknown"),
                    "usd": usd,
                    "logo": chain.get("logo_url", ""),
                })

        chains.sort(key=lambda x: x["usd"], reverse=True)

        return {
            "address": address,
            "type": "evm",
            "chains": chains,
            "total_usd": total,
            "error": None,
        }
    except Exception as e:
        return {
            "address": address,
            "type": "evm",
            "chains": [],
            "total_usd": 0,
            "error": str(e),
        }


def fetch_balance_for_url(url: str) -> dict:
    """Fetch balance for any tracked URL."""
    address, wallet_type = extract_address_from_url(url)
    if not address:
        return {"url": url, "error": "Could not extract address from URL", "total_usd": 0}

    if wallet_type == "solana":
        result = fetch_solana_balance(address)
    elif wallet_type == "evm":
        result = fetch_evm_balance(address)
    else:
        return {"url": url, "error": f"Unknown wallet type: {wallet_type}", "total_usd": 0}

    result["url"] = url
    return result


def fetch_all_balances(urls: list[dict]) -> list[dict]:
    """Fetch balances for all tracked URLs."""
    results = []
    for entry in urls:
        url = entry["url"]
        label = entry.get("label", url)
        result = fetch_balance_for_url(url)
        result["label"] = label
        results.append(result)
    return results
