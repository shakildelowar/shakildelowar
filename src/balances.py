"""Fetch wallet balances from Solana RPC and DeBank API."""

import requests
from urllib.parse import urlparse

SOLANA_RPCS = [
    "https://api.mainnet-beta.solana.com",
    "https://solana-rpc.publicnode.com",
    "https://rpc.ankr.com/solana",
]
JUPITER_PRICE_API = "https://api.jup.ag/price/v2"
COINGECKO_SOL_PRICE = "https://api.coingecko.com/api/v3/simple/price"
SOL_MINT = "So11111111111111111111111111111111111111112"
LAMPORTS_PER_SOL = 1_000_000_000

DEBANK_API = "https://api.debank.com/user/total_balance"


def _rpc_call(payload: dict, timeout: int = 15) -> dict | None:
    """Try multiple Solana RPC endpoints, return first successful response."""
    for rpc in SOLANA_RPCS:
        try:
            resp = requests.post(rpc, json=payload, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            if "error" not in data:
                return data
            print(f"[RPC] {rpc} returned error: {data.get('error')}")
        except Exception as e:
            print(f"[RPC] {rpc} failed: {e}")
    return None


def extract_address_from_url(url: str) -> tuple[str, str]:
    """Extract wallet address and type from a DeBank/Jupiter URL."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    path = parsed.path.rstrip("/")

    if "jup.ag" in host:
        parts = path.split("/")
        address = parts[-1] if len(parts) >= 2 else ""
        return address, "solana"
    elif "debank.com" in host:
        parts = path.split("/")
        address = parts[-1] if len(parts) >= 2 else ""
        return address, "evm"

    return "", "unknown"


def _sol_balance(address: str) -> float | None:
    data = _rpc_call({
        "jsonrpc": "2.0", "id": 1,
        "method": "getBalance",
        "params": [address],
    })
    if data:
        lamports = data.get("result", {}).get("value", 0)
        return lamports / LAMPORTS_PER_SOL
    return None


def _spl_tokens(address: str) -> list[dict]:
    """Get ALL SPL token accounts including Token-2022."""
    tokens = []

    for program_id in [
        "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
        "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",  # Token-2022
    ]:
        data = _rpc_call({
            "jsonrpc": "2.0", "id": 1,
            "method": "getTokenAccountsByOwner",
            "params": [
                address,
                {"programId": program_id},
                {"encoding": "jsonParsed"},
            ],
        })
        if data:
            accounts = data.get("result", {}).get("value", [])
            print(f"[Tokens] {program_id[:8]}... returned {len(accounts)} account(s)")
            for acct in accounts:
                info = acct["account"]["data"]["parsed"]["info"]
                mint = info.get("mint", "")
                ui_amount = info.get("tokenAmount", {}).get("uiAmount", 0)
                if ui_amount and ui_amount > 0:
                    tokens.append({"mint": mint, "amount": ui_amount})
        else:
            print(f"[Tokens] {program_id[:8]}... ALL RPCs failed")

    print(f"[Tokens] Total tokens with balance: {len(tokens)}")
    return tokens


def _token_prices(mints: list[str]) -> dict[str, float]:
    """Get prices from Jupiter, with CoinGecko fallback for SOL."""
    prices = {}

    # Jupiter Price API
    if mints:
        try:
            resp = requests.get(
                JUPITER_PRICE_API,
                params={"ids": ",".join(mints)},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            for m, info in data.items():
                if info.get("price"):
                    prices[m] = float(info["price"])
        except Exception:
            pass

    # Fallback: get SOL price from CoinGecko if Jupiter didn't return it
    if SOL_MINT not in prices:
        try:
            resp = requests.get(
                COINGECKO_SOL_PRICE,
                params={"ids": "solana", "vs_currencies": "usd"},
                timeout=10,
            )
            resp.raise_for_status()
            sol_price = resp.json().get("solana", {}).get("usd", 0)
            if sol_price:
                prices[SOL_MINT] = float(sol_price)
        except Exception:
            pass

    return prices


def _token_metadata(mints: list[str]) -> dict[str, dict]:
    """Get token names/symbols from Jupiter token list."""
    meta = {}
    # Always include SOL
    meta[SOL_MINT] = {"symbol": "SOL", "name": "Solana"}

    if not mints:
        return meta

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

    # Also try the "all" list for unverified tokens (like pumpfun tokens)
    unknown_mints = [m for m in mints if m not in meta]
    if unknown_mints:
        try:
            for mint in unknown_mints[:20]:  # Limit to avoid huge requests
                resp = requests.get(f"https://tokens.jup.ag/token/{mint}", timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    meta[mint] = {
                        "symbol": data.get("symbol", mint[:6] + "..."),
                        "name": data.get("name", "Unknown"),
                    }
        except Exception:
            pass

    return meta


def fetch_solana_balance(address: str) -> dict:
    """Fetch full Solana wallet balance with all tokens."""
    sol = _sol_balance(address)
    tokens = _spl_tokens(address)

    all_mints = [SOL_MINT] + [t["mint"] for t in tokens]
    prices = _token_prices(all_mints)
    metadata = _token_metadata(all_mints)

    sol_price = prices.get(SOL_MINT, 0)
    sol_usd = (sol or 0) * sol_price

    # Build token list - only include tokens worth >= $1
    MIN_USD_DISPLAY = 1.00
    token_list = []
    total_tokens_usd = 0.0

    for t in tokens:
        mint = t["mint"]
        amount = t["amount"]
        price = prices.get(mint, 0)
        usd = amount * price
        total_tokens_usd += usd

        # Skip tokens worth less than $1
        if usd < MIN_USD_DISPLAY:
            continue

        meta = metadata.get(mint, {})
        token_list.append({
            "mint": mint,
            "symbol": meta.get("symbol", mint[:8] + "..."),
            "name": meta.get("name", "Unknown"),
            "amount": amount,
            "price": price,
            "usd": usd,
        })

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
