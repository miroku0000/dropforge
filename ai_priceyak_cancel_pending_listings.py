"""
Cancel all pending PriceYak listing requests.

Usage:
    python ai_priceyak_cancel_pending_listings.py
"""

import requests

import config
ACCOUNT_ID = config.PY_ACCOUNT_ID
API_KEY = config.PY_API_KEY


def login():
    resp = requests.post(
        f"https://www.priceyak.com/v0/account/{ACCOUNT_ID}/api_login",
        json={"api_key": API_KEY},
    )
    resp.raise_for_status()
    return resp.json()["token"]


def cancel_pending(token):
    resp = requests.post(
        f"https://www.priceyak.com/v0/account/{ACCOUNT_ID}/requests/cancel",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + token,
        },
        json={},
    )
    print(f"Status: {resp.status_code}")
    print(resp.text)
    return resp


if __name__ == "__main__":
    token = login()
    cancel_pending(token)
