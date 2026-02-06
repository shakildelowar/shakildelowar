"""Fetch wallet balance from DeBank (EVM chains)."""

import requests

DEBANK_API_URL = "https://api.debank.com/user/total_balance"
DEBANK_PROFILE_URL = "https://debank.com/profile/{address}"


def fetch_debank_balance(address: str) -> dict:
    """Fetch total portfolio balance for an EVM address from DeBank.

    Returns dict with 'usd_value' and 'chain_balances'.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": DEBANK_PROFILE_URL.format(address=address),
    }

    try:
        resp = requests.get(
            DEBANK_API_URL,
            params={"addr": address.lower()},
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        total_usd = data.get("data", {}).get("total_usd_value", 0.0)
        chain_list = data.get("data", {}).get("chain_list", [])

        chain_balances = {}
        for chain in chain_list:
            chain_id = chain.get("community_id") or chain.get("id", "unknown")
            chain_balances[chain_id] = chain.get("usd_value", 0.0)

        return {
            "address": address,
            "source": "debank",
            "url": DEBANK_PROFILE_URL.format(address=address),
            "usd_value": total_usd,
            "chain_balances": chain_balances,
            "error": None,
        }

    except requests.RequestException as e:
        return {
            "address": address,
            "source": "debank",
            "url": DEBANK_PROFILE_URL.format(address=address),
            "usd_value": None,
            "chain_balances": {},
            "error": str(e),
        }
