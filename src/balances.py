"""Fetch wallet balances from Solana RPC, Solscan API, and DeBank API."""

import time
import requests
from urllib.parse import urlparse

SOLANA_RPCS = [
    "https://api.mainnet-beta.solana.com",
    "https://solana-rpc.publicnode.com",
    "https://rpc.ankr.com/solana",
    "https://solana.drpc.org",
]

# Well-known token registry: mint -> {symbol, name, stable_price}
# stable_price is used as a last-resort fallback when all price APIs fail
KNOWN_TOKENS = {
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": {"symbol": "USDC", "name": "USD Coin", "stable_price": 1.0},
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": {"symbol": "USDT", "name": "Tether USD", "stable_price": 1.0},
    "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN": {"symbol": "JUP", "name": "Jupiter"},
    "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263": {"symbol": "BONK", "name": "Bonk"},
    "jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL": {"symbol": "JTO", "name": "Jito"},
    "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs": {"symbol": "WETH", "name": "Wrapped Ether"},
    "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So": {"symbol": "mSOL", "name": "Marinade SOL"},
    "7dHbWXmci3dT8UFYWYZweBLXgycu7Y3iL6trKn1Y7ARj": {"symbol": "stSOL", "name": "Lido Staked SOL"},
    "bSo13r4TkiE4KumL71LsHTPpL2euBYLFx6h9HP3piy1": {"symbol": "bSOL", "name": "BlazeStake SOL"},
    "rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof": {"symbol": "RNDR", "name": "Render Token"},
}
KNOWN_MINTS = list(KNOWN_TOKENS.keys())
JUPITER_PRICE_API = "https://api.jup.ag/price/v2"
COINGECKO_SOL_PRICE = "https://api.coingecko.com/api/v3/simple/price"
SOL_MINT = "So11111111111111111111111111111111111111112"
LAMPORTS_PER_SOL = 1_000_000_000

DEBANK_API = "https://api.debank.com/user/total_balance"

# Threshold for splitting tokens into "Holdings" vs "Other"
HOLDINGS_THRESHOLD = 1.00


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


def _spl_tokens_via_program(address: str) -> list[dict]:
    """Get ALL SPL token accounts by querying program IDs (heavy call)."""
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
        }, timeout=20)
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

    return tokens


def _spl_tokens_by_mint(address: str) -> list[dict]:
    """Fallback: query known token mints individually (lighter calls)."""
    tokens = []
    print(f"[Tokens] Falling back to individual mint queries...")

    for mint in KNOWN_MINTS:
        data = _rpc_call({
            "jsonrpc": "2.0", "id": 1,
            "method": "getTokenAccountsByOwner",
            "params": [
                address,
                {"mint": mint},
                {"encoding": "jsonParsed"},
            ],
        }, timeout=10)
        if data:
            accounts = data.get("result", {}).get("value", [])
            for acct in accounts:
                info = acct["account"]["data"]["parsed"]["info"]
                ui_amount = info.get("tokenAmount", {}).get("uiAmount", 0)
                if ui_amount and ui_amount > 0:
                    tokens.append({"mint": mint, "amount": ui_amount})
                    print(f"[Tokens] Found {mint[:8]}... = {ui_amount}")
        # Small delay to avoid rate limiting on sequential calls
        time.sleep(0.2)

    return tokens


def _spl_tokens_via_solscan(address: str) -> list[dict]:
    """Fallback: use Solscan V2 API (REST, no RPC needed)."""
    tokens = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Origin": "https://solscan.io",
    }
    try:
        resp = requests.get(
            f"https://api-v2.solscan.io/v2/account/token-accounts",
            params={"address": address, "type": "token", "page": 1, "page_size": 40},
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", {}).get("token_accounts", []) if isinstance(data.get("data"), dict) else data.get("data", [])
        for item in items:
            amount = item.get("amount", 0)
            decimals = item.get("token_decimals", 0)
            mint = item.get("token_address", "")
            if amount and decimals and mint:
                ui_amount = amount / (10 ** decimals)
                if ui_amount > 0:
                    tokens.append({"mint": mint, "amount": ui_amount})
        print(f"[Solscan] Returned {len(tokens)} token(s)")
    except Exception as e:
        print(f"[Solscan] Failed: {e}")

    # Also try Token-2022 accounts
    try:
        resp = requests.get(
            f"https://api-v2.solscan.io/v2/account/token-accounts",
            params={"address": address, "type": "token", "page": 1, "page_size": 40,
                    "token_type": "token2022"},
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", {}).get("token_accounts", []) if isinstance(data.get("data"), dict) else data.get("data", [])
        for item in items:
            amount = item.get("amount", 0)
            decimals = item.get("token_decimals", 0)
            mint = item.get("token_address", "")
            if amount and decimals and mint:
                ui_amount = amount / (10 ** decimals)
                if ui_amount > 0:
                    tokens.append({"mint": mint, "amount": ui_amount})
        print(f"[Solscan Token-2022] Returned {len(tokens)} total token(s)")
    except Exception as e:
        print(f"[Solscan Token-2022] Failed: {e}")

    return tokens


def _spl_tokens(address: str) -> list[dict]:
    """Get SPL token accounts. Tries multiple strategies."""
    # Strategy 1: Full program scan via RPC
    tokens = _spl_tokens_via_program(address)
    if tokens:
        print(f"[Tokens] Got {len(tokens)} from RPC program scan")
        return tokens

    # Strategy 2: Solscan REST API (no RPC needed, different rate limits)
    tokens = _spl_tokens_via_solscan(address)
    if tokens:
        print(f"[Tokens] Got {len(tokens)} from Solscan API")
        return tokens

    # Strategy 3: Query known mints individually via RPC
    tokens = _spl_tokens_by_mint(address)
    if tokens:
        print(f"[Tokens] Got {len(tokens)} from individual mint queries")

    print(f"[Tokens] Total tokens with balance: {len(tokens)}")
    return tokens


def _token_prices(mints: list[str]) -> dict[str, float]:
    """Get prices from Jupiter, with CoinGecko fallback for SOL and hardcoded stablecoin prices."""
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
            print(f"[Prices] Jupiter returned {len(prices)} price(s)")
        except Exception as e:
            print(f"[Prices] Jupiter failed: {e}")

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
                print(f"[Prices] CoinGecko SOL: ${sol_price}")
        except Exception as e:
            print(f"[Prices] CoinGecko also failed: {e}")

    # Last resort: use hardcoded stablecoin prices for any missing known tokens
    for mint in mints:
        if mint not in prices and mint in KNOWN_TOKENS:
            stable = KNOWN_TOKENS[mint].get("stable_price")
            if stable:
                prices[mint] = stable
                print(f"[Prices] Using hardcoded price for {KNOWN_TOKENS[mint]['symbol']}: ${stable}")

    return prices


def _token_metadata(mints: list[str]) -> dict[str, dict]:
    """Get token names/symbols. Uses hardcoded registry + Jupiter API."""
    meta = {}
    # Always include SOL
    meta[SOL_MINT] = {"symbol": "SOL", "name": "Solana"}

    # Start with hardcoded known tokens (always works)
    for mint in mints:
        if mint in KNOWN_TOKENS:
            meta[mint] = {
                "symbol": KNOWN_TOKENS[mint]["symbol"],
                "name": KNOWN_TOKENS[mint]["name"],
            }

    if not mints:
        return meta

    # Try Jupiter verified token list to get any we missed
    unknown_mints = [m for m in mints if m not in meta]
    if unknown_mints:
        try:
            resp = requests.get("https://tokens.jup.ag/tokens?tags=verified", timeout=10)
            resp.raise_for_status()
            for token in resp.json():
                addr = token.get("address")
                if addr in unknown_mints:
                    meta[addr] = {
                        "symbol": token.get("symbol", "???"),
                        "name": token.get("name", "Unknown"),
                    }
        except Exception as e:
            print(f"[Metadata] Jupiter verified list failed: {e}")

    # Individual lookup for still-unknown tokens (pumpfun etc.)
    still_unknown = [m for m in mints if m not in meta]
    for mint in still_unknown[:20]:
        try:
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

    # Build ALL tokens with metadata and prices
    all_token_items = []
    total_tokens_usd = 0.0

    for t in tokens:
        mint = t["mint"]
        amount = t["amount"]
        price = prices.get(mint, 0)
        usd = amount * price
        total_tokens_usd += usd
        meta = metadata.get(mint, {})

        all_token_items.append({
            "mint": mint,
            "symbol": meta.get("symbol", mint[:8] + "..."),
            "name": meta.get("name", "Unknown"),
            "amount": amount,
            "price": price,
            "usd": usd,
        })

    # Split into holdings (>= threshold) and other (< threshold)
    holdings = [t for t in all_token_items if t["usd"] >= HOLDINGS_THRESHOLD]
    other = [t for t in all_token_items if t["usd"] < HOLDINGS_THRESHOLD]

    holdings.sort(key=lambda x: x["usd"], reverse=True)
    other.sort(key=lambda x: x["usd"], reverse=True)

    return {
        "address": address,
        "type": "solana",
        "sol_balance": sol,
        "sol_price": sol_price,
        "sol_usd": sol_usd,
        "tokens": holdings,
        "other_tokens": other,
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
