"""Fetch wallet balance from Jupiter / Solana."""

import requests

JUPITER_PORTFOLIO_URL = "https://jup.ag/portfolio/{address}"
SOLANA_PUBLIC_RPC = "https://api.mainnet-beta.solana.com"
# Token price endpoint from Jupiter
JUPITER_PRICE_API = "https://api.jup.ag/price/v2"
# SOL mint address
SOL_MINT = "So11111111111111111111111111111111111111112"
LAMPORTS_PER_SOL = 1_000_000_000


def _get_sol_balance(address: str) -> float | None:
    """Get native SOL balance via Solana RPC."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getBalance",
        "params": [address],
    }
    try:
        resp = requests.post(SOLANA_PUBLIC_RPC, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        lamports = data.get("result", {}).get("value", 0)
        return lamports / LAMPORTS_PER_SOL
    except requests.RequestException:
        return None


def _get_token_accounts(address: str) -> list[dict]:
    """Get all SPL token accounts for an address."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTokenAccountsByOwner",
        "params": [
            address,
            {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
            {"encoding": "jsonParsed"},
        ],
    }
    try:
        resp = requests.post(SOLANA_PUBLIC_RPC, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        accounts = data.get("result", {}).get("value", [])

        tokens = []
        for acct in accounts:
            info = acct.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
            mint = info.get("mint", "")
            token_amount = info.get("tokenAmount", {})
            ui_amount = token_amount.get("uiAmount", 0)
            if ui_amount and ui_amount > 0:
                tokens.append({"mint": mint, "amount": ui_amount})
        return tokens
    except requests.RequestException:
        return []


def _get_token_prices(mints: list[str]) -> dict[str, float]:
    """Get USD prices for tokens via Jupiter Price API."""
    if not mints:
        return {}
    try:
        resp = requests.get(
            JUPITER_PRICE_API,
            params={"ids": ",".join(mints)},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        prices = {}
        for mint, info in data.items():
            price = info.get("price")
            if price is not None:
                prices[mint] = float(price)
        return prices
    except requests.RequestException:
        return {}


def fetch_jupiter_balance(address: str) -> dict:
    """Fetch total portfolio value for a Solana address.

    Uses Solana RPC for balances and Jupiter Price API for USD values.
    """
    try:
        # Get native SOL balance
        sol_balance = _get_sol_balance(address)

        # Get SPL token balances
        token_accounts = _get_token_accounts(address)

        # Collect all mints for price lookup (include SOL)
        all_mints = [SOL_MINT] + [t["mint"] for t in token_accounts]
        prices = _get_token_prices(all_mints)

        # Calculate SOL value
        sol_price = prices.get(SOL_MINT, 0)
        sol_usd = (sol_balance or 0) * sol_price

        # Calculate token values
        token_balances = {}
        total_token_usd = 0.0
        for token in token_accounts:
            mint = token["mint"]
            amount = token["amount"]
            price = prices.get(mint, 0)
            usd_val = amount * price
            if usd_val > 0.01:  # skip dust
                token_balances[mint] = {
                    "amount": amount,
                    "price": price,
                    "usd_value": usd_val,
                }
                total_token_usd += usd_val

        total_usd = sol_usd + total_token_usd

        return {
            "address": address,
            "source": "jupiter",
            "url": JUPITER_PORTFOLIO_URL.format(address=address),
            "usd_value": total_usd,
            "sol_balance": sol_balance,
            "sol_usd": sol_usd,
            "token_balances": token_balances,
            "error": None,
        }

    except Exception as e:
        return {
            "address": address,
            "source": "jupiter",
            "url": JUPITER_PORTFOLIO_URL.format(address=address),
            "usd_value": None,
            "sol_balance": None,
            "sol_usd": None,
            "token_balances": {},
            "error": str(e),
        }
