"""Fetch wallet balances from Solana RPC, Solscan API, and DeBank API."""

import os
import time
import requests
from urllib.parse import urlparse

SOLANA_RPCS = [
    "https://solana-rpc.publicnode.com",
    "https://rpc.ankr.com/solana",
    "https://solana.drpc.org",
    "https://solana-mainnet.rpc.extrnode.com",
    "https://rpc.solana.gateway.fm",
    "https://api.mainnet-beta.solana.com",
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
ANKR_MULTICHAIN = "https://rpc.ankr.com/multichain"

# Ankr API key from environment variable
_ankr_api_key = os.environ.get("ANKR_API_KEY", "").strip()

# Public RPC endpoints for direct chain queries (ultimate fallback)
EVM_CHAINS = {
    "ethereum": {
        "rpcs": [
            "https://ethereum-rpc.publicnode.com",
            "https://eth.drpc.org",
            "https://1rpc.io/eth",
            "https://rpc.mevblocker.io",
            "https://eth.llamarpc.com",
            "https://cloudflare-eth.com",
            "https://rpc.ankr.com/eth",
        ],
        "native": "ETH",
        "decimals": 18,
        "coingecko_id": "ethereum",
        "binance_symbol": "ETHUSDT",
        "blockscout": "https://eth.blockscout.com",
    },
    "polygon": {
        "rpcs": ["https://polygon-bor-rpc.publicnode.com", "https://polygon-rpc.com", "https://rpc.ankr.com/polygon", "https://polygon.drpc.org"],
        "native": "POL",
        "decimals": 18,
        "coingecko_id": "polygon-ecosystem-token",
        "binance_symbol": "POLUSDT",
        "blockscout": "https://polygon.blockscout.com",
    },
    "bsc": {
        "rpcs": ["https://bsc-rpc.publicnode.com", "https://bsc-dataseed.binance.org", "https://rpc.ankr.com/bsc", "https://bsc.drpc.org"],
        "native": "BNB",
        "decimals": 18,
        "coingecko_id": "binancecoin",
        "binance_symbol": "BNBUSDT",
        "blockscout": None,  # BSC Blockscout is down
        "bscscan": "https://api.bscscan.com/api",
    },
    "arbitrum": {
        "rpcs": ["https://arbitrum-one-rpc.publicnode.com", "https://arb1.arbitrum.io/rpc", "https://rpc.ankr.com/arbitrum"],
        "native": "ETH",
        "decimals": 18,
        "coingecko_id": "ethereum",
        "binance_symbol": "ETHUSDT",
        "blockscout": "https://arbitrum.blockscout.com",
    },
    "optimism": {
        "rpcs": ["https://mainnet.optimism.io", "https://rpc.ankr.com/optimism"],
        "native": "ETH",
        "decimals": 18,
        "coingecko_id": "ethereum",
        "binance_symbol": "ETHUSDT",
        "blockscout": "https://optimism.blockscout.com",
    },
    "base": {
        "rpcs": ["https://mainnet.base.org", "https://rpc.ankr.com/base"],
        "native": "ETH",
        "decimals": 18,
        "coingecko_id": "ethereum",
        "binance_symbol": "ETHUSDT",
        "blockscout": "https://base.blockscout.com",
    },
    "avalanche": {
        "rpcs": ["https://api.avax.network/ext/bc/C/rpc", "https://rpc.ankr.com/avalanche"],
        "native": "AVAX",
        "decimals": 18,
        "coingecko_id": "avalanche-2",
        "binance_symbol": "AVAXUSDT",
        "blockscout": None,
    },
}

# Threshold for splitting tokens into "Holdings" vs "Other"
HOLDINGS_THRESHOLD = 1.00


def _rpc_call(payload: dict, timeout: int = 6) -> dict | None:
    """Try multiple Solana RPC endpoints, return first successful response."""
    for rpc in SOLANA_RPCS:
        try:
            resp = requests.post(rpc, json=payload, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            if "error" not in data:
                return data
        except Exception:
            pass
    return None


def extract_address_from_url(url: str) -> tuple[str, str]:
    """Extract wallet address and type from a DeBank/Jupiter/Zerion URL."""
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
    elif "zerion.io" in host:
        # Zerion URL: https://app.zerion.io/{address}/overview
        parts = [p for p in path.split("/") if p]
        address = parts[0] if parts else ""
        # Solana addresses are base58 (no 0x prefix), EVM starts with 0x
        if address.startswith("0x"):
            return address, "evm"
        else:
            return address, "solana"
    elif "solscan.io" in host:
        # Solscan URL: https://solscan.io/account/{address}
        parts = [p for p in path.split("/") if p]
        # Find the part after "account"
        if "account" in parts:
            idx = parts.index("account")
            address = parts[idx + 1] if idx + 1 < len(parts) else ""
        else:
            address = parts[-1] if parts else ""
        return address, "solana"

    return "", "unknown"


SOLSCAN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Origin": "https://solscan.io",
}


def _sol_balance(address: str) -> float | None:
    """Get SOL balance via Solscan first (most reliable), then RPC fallback."""
    # Strategy 1: Solscan account API (fastest, most reliable from cloud)
    try:
        resp = requests.get(
            f"https://api-v2.solscan.io/v2/account?address={address}",
            headers=SOLSCAN_HEADERS,
            timeout=8,
        )
        resp.raise_for_status()
        d = resp.json().get("data", {})
        sol_lamports = d.get("lamports")
        if sol_lamports is not None:
            balance = int(sol_lamports) / LAMPORTS_PER_SOL
            print(f"[Solscan] SOL balance: {balance}")
            return balance
    except Exception as e:
        print(f"[Solscan] Account balance failed: {e}")

    # Strategy 2: Solana RPC
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
        }, timeout=8)
        if data:
            accounts = data.get("result", {}).get("value", [])
            for acct in accounts:
                info = acct["account"]["data"]["parsed"]["info"]
                mint = info.get("mint", "")
                ui_amount = info.get("tokenAmount", {}).get("uiAmount", 0)
                if ui_amount and ui_amount > 0:
                    tokens.append({"mint": mint, "amount": ui_amount})

    return tokens


def _spl_tokens_by_mint(address: str) -> list[dict]:
    """Fallback: query known token mints individually (lighter calls)."""
    tokens = []
    # Only check top 4 known mints to keep it fast
    for mint in KNOWN_MINTS[:4]:
        data = _rpc_call({
            "jsonrpc": "2.0", "id": 1,
            "method": "getTokenAccountsByOwner",
            "params": [
                address,
                {"mint": mint},
                {"encoding": "jsonParsed"},
            ],
        }, timeout=5)
        if data:
            accounts = data.get("result", {}).get("value", [])
            for acct in accounts:
                info = acct["account"]["data"]["parsed"]["info"]
                ui_amount = info.get("tokenAmount", {}).get("uiAmount", 0)
                if ui_amount and ui_amount > 0:
                    tokens.append({"mint": mint, "amount": ui_amount})

    return tokens


def _spl_tokens_via_solscan(address: str) -> list[dict]:
    """Use Solscan V2 REST API for token balances (no RPC needed)."""
    tokens = []

    # New Solscan V2 endpoint: /v2/account/tokens
    try:
        resp = requests.get(
            f"https://api-v2.solscan.io/v2/account/tokens",
            params={"address": address},
            headers=SOLSCAN_HEADERS,
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", {}).get("tokens", [])
        if not items and isinstance(data.get("data"), list):
            items = data.get("data", [])

        for item in items:
            mint = item.get("tokenAddress", "")
            balance = item.get("balance", 0)
            decimals = item.get("decimals", 0)
            amount_raw = item.get("amount", 0)

            # Prefer pre-calculated balance, fallback to raw amount
            ui_amount = float(balance) if balance else 0
            if not ui_amount and amount_raw and decimals:
                ui_amount = int(amount_raw) / (10 ** int(decimals))

            if ui_amount > 0 and mint:
                tokens.append({"mint": mint, "amount": ui_amount})

        print(f"[Solscan] Returned {len(tokens)} token(s)")
    except Exception as e:
        print(f"[Solscan] Failed: {e}")

    # Fallback: old endpoint format (token-accounts)
    if not tokens:
        try:
            resp = requests.get(
                f"https://api-v2.solscan.io/v2/account/token-accounts",
                params={"address": address, "type": "token", "page": 1, "page_size": 40},
                headers=SOLSCAN_HEADERS,
                timeout=8,
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("data", {}).get("token_accounts", []) if isinstance(data.get("data"), dict) else data.get("data", [])
            for item in items:
                amount = item.get("amount", 0)
                decimals = item.get("token_decimals", 0)
                mint = item.get("token_address", "")
                if amount and decimals and mint:
                    ui_amount = int(amount) / (10 ** int(decimals))
                    if ui_amount > 0:
                        tokens.append({"mint": mint, "amount": ui_amount})
            print(f"[Solscan fallback] Returned {len(tokens)} token(s)")
        except Exception as e:
            print(f"[Solscan fallback] Failed: {e}")

    return tokens


def _spl_tokens(address: str) -> list[dict]:
    """Get SPL token accounts. Tries multiple strategies."""
    # Strategy 1: Solscan REST API (most reliable from cloud IPs)
    tokens = _spl_tokens_via_solscan(address)
    if tokens:
        print(f"[Tokens] Got {len(tokens)} from Solscan API")
        return tokens

    # Strategy 2: Full program scan via RPC
    tokens = _spl_tokens_via_program(address)
    if tokens:
        print(f"[Tokens] Got {len(tokens)} from RPC program scan")
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
                timeout=8,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            for m, info in data.items():
                if info.get("price"):
                    prices[m] = float(info["price"])
            print(f"[Prices] Jupiter returned {len(prices)} price(s)")
        except Exception as e:
            print(f"[Prices] Jupiter failed: {e}")

    # Fallback 1: CoinGecko for SOL
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
            print(f"[Prices] CoinGecko failed: {e}")

    # Fallback 2: Binance for SOL
    if SOL_MINT not in prices:
        try:
            resp = requests.get(
                "https://api.binance.com/api/v3/ticker/price",
                params={"symbol": "SOLUSDT"},
                timeout=10,
            )
            resp.raise_for_status()
            sol_price = float(resp.json().get("price", 0))
            if sol_price:
                prices[SOL_MINT] = sol_price
                print(f"[Prices] Binance SOL: ${sol_price}")
        except Exception as e:
            print(f"[Prices] Binance failed: {e}")

    # Fallback 3: CoinCap for SOL
    if SOL_MINT not in prices:
        try:
            resp = requests.get(
                "https://api.coincap.io/v2/assets/solana",
                timeout=10,
            )
            resp.raise_for_status()
            sol_price = float(resp.json().get("data", {}).get("priceUsd", 0))
            if sol_price:
                prices[SOL_MINT] = sol_price
                print(f"[Prices] CoinCap SOL: ${sol_price}")
        except Exception as e:
            print(f"[Prices] CoinCap failed: {e}")

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

    # Build token list - only include tokens that have a price
    # (stablecoins always have hardcoded $1.00, others need live API price)
    all_token_items = []
    total_tokens_usd = 0.0

    for t in tokens:
        mint = t["mint"]
        amount = t["amount"]
        price = prices.get(mint, 0)
        usd = amount * price
        total_tokens_usd += usd

        # Skip tokens without a price (no reliable data)
        if price == 0:
            continue

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


def _evm_balance_ankr(address: str) -> dict | None:
    """Fetch EVM balance via Ankr multichain API with retry."""
    if not _ankr_api_key:
        print("[Ankr] No API key set, skipping")
        return None

    ankr_url = f"{ANKR_MULTICHAIN}/{_ankr_api_key}"
    for attempt in range(2):
        try:
            resp = requests.post(ankr_url, json={
                "jsonrpc": "2.0", "id": 1,
                "method": "ankr_getAccountBalance",
                "params": {"walletAddress": address.lower()},
            }, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                print(f"[Ankr] Error (attempt {attempt+1}): {data['error']}")
                if attempt < 1:
                    time.sleep(1)
                    continue
                return None

            assets = data.get("result", {}).get("assets", [])
            total = float(data.get("result", {}).get("totalBalanceUsd", 0))

            chain_totals = {}
            for asset in assets:
                chain = asset.get("blockchain", "unknown")
                usd = float(asset.get("balanceUsd", 0))
                if chain not in chain_totals:
                    chain_totals[chain] = {"name": chain.upper(), "usd": 0}
                chain_totals[chain]["usd"] += usd

            chains = [v for v in chain_totals.values() if v["usd"] > 0.01]
            chains.sort(key=lambda x: x["usd"], reverse=True)

            tokens = []
            for asset in assets:
                usd = float(asset.get("balanceUsd", 0))
                if usd > 0.01:
                    tokens.append({
                        "symbol": asset.get("tokenSymbol", "???"),
                        "name": asset.get("tokenName", "Unknown"),
                        "amount": float(asset.get("balance", 0)),
                        "price": float(asset.get("tokenPrice", 0)),
                        "usd": usd,
                        "chain": asset.get("blockchain", ""),
                    })
            tokens.sort(key=lambda x: x["usd"], reverse=True)

            print(f"[Ankr] Found {len(assets)} assets, total ${total:.2f}")
            return {
                "address": address,
                "type": "evm",
                "chains": chains,
                "evm_tokens": tokens,
                "total_usd": total,
                "error": None,
            }
        except Exception as e:
            print(f"[Ankr] Attempt {attempt+1} failed: {e}")
            if attempt < 1:
                time.sleep(1)
    return None


def _fetch_evm_prices() -> dict:
    """Get native EVM token prices from CoinGecko, with Binance fallback."""
    coingecko_ids = list(set(c["coingecko_id"] for c in EVM_CHAINS.values()))
    prices = {}

    # Try CoinGecko first
    try:
        resp = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": ",".join(coingecko_ids), "vs_currencies": "usd"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        for cg_id, vals in data.items():
            prices[cg_id] = vals.get("usd", 0)
        print(f"[Prices] CoinGecko EVM prices: {prices}")
    except Exception as e:
        print(f"[Prices] CoinGecko EVM prices failed: {e}")

    # Binance fallback for any missing prices
    binance_symbols = set()
    for chain_info in EVM_CHAINS.values():
        cg_id = chain_info["coingecko_id"]
        if cg_id not in prices or prices[cg_id] == 0:
            binance_symbols.add((chain_info["binance_symbol"], cg_id))

    for binance_sym, cg_id in binance_symbols:
        try:
            resp = requests.get(
                "https://api.binance.com/api/v3/ticker/price",
                params={"symbol": binance_sym},
                timeout=10,
            )
            resp.raise_for_status()
            price = float(resp.json().get("price", 0))
            if price:
                prices[cg_id] = price
                print(f"[Prices] Binance {binance_sym}: ${price}")
        except Exception as e:
            print(f"[Prices] Binance {binance_sym} failed: {e}")

    return prices


def _fetch_blockscout_tokens(address: str, chain_name: str, blockscout_url: str) -> list[dict]:
    """Fetch ERC-20 token balances from Blockscout API (free, no key)."""
    tokens = []
    try:
        resp = requests.get(
            f"{blockscout_url}/api/v2/addresses/{address.lower()}/token-balances",
            timeout=8,
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()

        for item in data:
            token_info = item.get("token", {})
            raw_value = item.get("value", "0")
            decimals = int(token_info.get("decimals") or 18)
            symbol = token_info.get("symbol", "???")
            name = token_info.get("name", "Unknown")
            exchange_rate = token_info.get("exchange_rate")

            balance = int(raw_value) / (10 ** decimals) if raw_value else 0
            if balance < 0.000001:
                continue

            price = float(exchange_rate) if exchange_rate else 0
            usd = balance * price

            tokens.append({
                "symbol": symbol,
                "name": name,
                "amount": balance,
                "price": price,
                "usd": usd,
                "chain": chain_name,
            })

        print(f"[Blockscout] {chain_name}: {len(tokens)} token(s)")
    except Exception as e:
        print(f"[Blockscout] {chain_name} failed: {e}")

    return tokens


def _fetch_bscscan_tokens(address: str) -> list[dict]:
    """Fetch BSC ERC-20 tokens via BscScan tokentx endpoint (free, no key, rate-limited)."""
    tokens = []
    try:
        # Get recent token transfers to discover which tokens this address holds
        resp = requests.get(
            "https://api.bscscan.com/api",
            params={
                "module": "account",
                "action": "tokentx",
                "address": address.lower(),
                "page": 1,
                "offset": 50,
                "sort": "desc",
            },
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "1":
            print(f"[BscScan] tokentx: {data.get('message', 'error')}")
            return tokens

        # Collect unique token contracts
        seen_contracts = {}
        for tx in data.get("result", []):
            contract = tx.get("contractAddress", "")
            if contract and contract not in seen_contracts:
                seen_contracts[contract] = {
                    "symbol": tx.get("tokenSymbol", "???"),
                    "name": tx.get("tokenName", "Unknown"),
                    "decimals": int(tx.get("tokenDecimal", 18)),
                }

        if not seen_contracts:
            return tokens

        print(f"[BscScan] Found {len(seen_contracts)} unique token contract(s)")

        # Check balance of each token (rate limit: 1 call per 5s without key)
        # Only check top 5 to stay within rate limits
        for i, (contract, meta) in enumerate(list(seen_contracts.items())[:5]):
            if i > 0:
                time.sleep(0.3)  # Small delay to avoid rate limit
            try:
                resp = requests.get(
                    "https://api.bscscan.com/api",
                    params={
                        "module": "account",
                        "action": "tokenbalance",
                        "contractaddress": contract,
                        "address": address.lower(),
                        "tag": "latest",
                    },
                    timeout=6,
                )
                resp.raise_for_status()
                bal_data = resp.json()
                if bal_data.get("status") == "1":
                    raw = int(bal_data.get("result", "0"))
                    balance = raw / (10 ** meta["decimals"])
                    if balance > 0.000001:
                        tokens.append({
                            "symbol": meta["symbol"],
                            "name": meta["name"],
                            "amount": balance,
                            "price": 0,  # BscScan doesn't provide prices
                            "usd": 0,
                            "chain": "bsc",
                            "contract": contract,
                        })
            except Exception as e:
                print(f"[BscScan] Balance check failed for {meta['symbol']}: {e}")

        print(f"[BscScan] {len(tokens)} token(s) with balance")
    except Exception as e:
        print(f"[BscScan] Failed: {e}")

    return tokens


def _evm_balance_direct_rpc(address: str) -> dict | None:
    """Fallback: query each chain's public RPC for native balance + Blockscout for ERC-20."""
    chains = []
    evm_tokens = []
    total_usd = 0

    prices = _fetch_evm_prices()
    active_chains = []  # chains where the address has native balance

    for chain_name, chain_info in EVM_CHAINS.items():
        for rpc_url in chain_info["rpcs"]:
            try:
                resp = requests.post(rpc_url, json={
                    "jsonrpc": "2.0", "id": 1,
                    "method": "eth_getBalance",
                    "params": [address.lower(), "latest"],
                }, timeout=6)
                resp.raise_for_status()
                data = resp.json()
                if "error" in data:
                    continue

                hex_balance = data.get("result", "0x0")
                wei = int(hex_balance, 16)
                balance = wei / (10 ** chain_info["decimals"])

                if balance < 0.000001:
                    # Still mark chain as active if Blockscout might have tokens
                    active_chains.append(chain_name)
                    break

                price = prices.get(chain_info["coingecko_id"], 0)
                usd = balance * price

                chains.append({"name": chain_name.upper(), "usd": usd})
                evm_tokens.append({
                    "symbol": chain_info["native"],
                    "name": f"{chain_name.title()}",
                    "amount": balance,
                    "price": price,
                    "usd": usd,
                    "chain": chain_name,
                })
                total_usd += usd
                active_chains.append(chain_name)
                print(f"[DirectRPC] {chain_name}: {balance:.6f} {chain_info['native']} = ${usd:.2f}")
                break
            except Exception as e:
                print(f"[DirectRPC] {chain_name} {rpc_url} failed: {e}")
                continue

    # Fetch ERC-20 tokens via Blockscout/BscScan for chains with activity
    for chain_name in active_chains:
        chain_info = EVM_CHAINS[chain_name]
        chain_tokens = []

        # Try Blockscout first (works for Ethereum, Polygon, etc.)
        blockscout_url = chain_info.get("blockscout")
        if blockscout_url:
            chain_tokens = _fetch_blockscout_tokens(address, chain_name, blockscout_url)

        # Try BscScan for BSC
        if not chain_tokens and chain_name == "bsc":
            chain_tokens = _fetch_bscscan_tokens(address)

        for t in chain_tokens:
            if t["usd"] > 0.01:
                evm_tokens.append(t)
                total_usd += t["usd"]
                # Add to chain total
                existing = next((c for c in chains if c["name"] == chain_name.upper()), None)
                if existing:
                    existing["usd"] += t["usd"]
                else:
                    chains.append({"name": chain_name.upper(), "usd": t["usd"]})

    if not chains and not evm_tokens:
        return None

    chains.sort(key=lambda x: x["usd"], reverse=True)
    evm_tokens.sort(key=lambda x: x["usd"], reverse=True)

    return {
        "address": address,
        "type": "evm",
        "chains": chains,
        "evm_tokens": evm_tokens,
        "total_usd": total_usd,
        "error": None,
    }


def _evm_balance_debank(address: str) -> dict | None:
    """Fallback: Fetch EVM balance via DeBank API."""
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
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        total = data.get("total_usd_value", 0.0)
        chains = []
        for chain in data.get("chain_list", []):
            usd = chain.get("usd_value", 0)
            if usd > 0.01:
                chains.append({
                    "name": chain.get("name", "Unknown"),
                    "usd": usd,
                })
        chains.sort(key=lambda x: x["usd"], reverse=True)
        return {
            "address": address,
            "type": "evm",
            "chains": chains,
            "evm_tokens": [],
            "total_usd": total,
            "error": None,
        }
    except Exception as e:
        print(f"[DeBank] Failed: {e}")
        return None


def fetch_evm_balance(address: str) -> dict:
    """Fetch EVM wallet balance. Tries Ankr (if key), then direct RPC + Blockscout."""
    # Strategy 1: Ankr (requires free API key)
    result = _evm_balance_ankr(address)
    if result:
        return result

    # Strategy 2: Direct chain RPCs + Blockscout for ERC-20 tokens
    print("[EVM] Trying direct chain RPCs + Blockscout...")
    result = _evm_balance_direct_rpc(address)
    if result:
        return result

    # Strategy 3: DeBank (often blocked from server IPs)
    print("[EVM] Trying DeBank as last resort...")
    result = _evm_balance_debank(address)
    if result:
        return result

    return {
        "address": address,
        "type": "evm",
        "chains": [],
        "evm_tokens": [],
        "total_usd": 0,
        "error": "Could not fetch EVM balance. Try again later.",
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
