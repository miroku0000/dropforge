"""
eBay OAuth Token Refresh (no browser needed)
Uses the refresh token from credentials.txt to get a fresh access token.
The refresh token lasts 18 months. When it expires, run ai_ebay_get_oauth_token.py
to get a new one via the developer portal.

Usage:
    python ai_ebay_refresh_oauth_token.py
"""

import requests
import base64
import logging
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ebay_ads_automation.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"

SCOPES = " ".join([
    "https://api.ebay.com/oauth/api_scope",
    "https://api.ebay.com/oauth/api_scope/sell.marketing.readonly",
    "https://api.ebay.com/oauth/api_scope/sell.marketing",
    "https://api.ebay.com/oauth/api_scope/sell.inventory.readonly",
    "https://api.ebay.com/oauth/api_scope/sell.inventory",
    "https://api.ebay.com/oauth/api_scope/sell.account.readonly",
    "https://api.ebay.com/oauth/api_scope/sell.account",
    "https://api.ebay.com/oauth/api_scope/sell.fulfillment.readonly",
    "https://api.ebay.com/oauth/api_scope/sell.fulfillment",
    "https://api.ebay.com/oauth/api_scope/sell.analytics.readonly",
    "https://api.ebay.com/oauth/api_scope/sell.finances",
    "https://api.ebay.com/oauth/api_scope/sell.payment.dispute",
    "https://api.ebay.com/oauth/api_scope/commerce.identity.readonly",
])


def load_credentials():
    """Load credentials from credentials.txt."""
    creds = {}
    with open("credentials.txt", "r") as f:
        for line in f:
            if "=" in line and not line.strip().startswith("#"):
                key, val = line.strip().split("=", 1)
                creds[key.strip()] = val.strip()
    return creds


def refresh_token():
    """Use refresh_token to get a new access token."""
    creds = load_credentials()

    app_id = creds.get("appid", "")
    cert_id = creds.get("certid", "")
    refresh_tok = creds.get("refresh_token", "")

    if not refresh_tok:
        log.error("No refresh_token found in credentials.txt")
        log.error("Run ai_ebay_get_oauth_token.py to get one via the developer portal")
        return False

    auth_b64 = base64.b64encode(f"{app_id}:{cert_id}".encode()).decode()

    log.info("Refreshing eBay OAuth token...")
    resp = requests.post(
        TOKEN_URL,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {auth_b64}",
        },
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_tok,
            "scope": SCOPES,
        },
        timeout=30,
    )

    if resp.status_code != 200:
        log.error(f"Token refresh failed ({resp.status_code}): {resp.text}")
        log.error("Your refresh token may have expired. Run ai_ebay_get_oauth_token.py to get a new one.")
        return False

    token_data = resp.json()
    new_token = token_data["access_token"]
    expires_in = token_data["expires_in"]

    log.info(f"Token refreshed successfully (expires in {expires_in/3600:.1f} hours)")

    # Save to credentials.txt
    save_token(new_token, expires_in)
    return True


def save_token(new_token, expires_in):
    """Update credentials.txt with the new token."""
    now = datetime.now()
    expiry = now + timedelta(seconds=expires_in)

    with open("credentials.txt", "r") as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        if line.startswith("token="):
            new_lines.append(f"token={new_token}\n")
        elif line.startswith("token_expiry="):
            new_lines.append(f"token_expiry={expiry.isoformat()}\n")
        elif line.startswith("# Token expires at:"):
            new_lines.append(f"# Token expires at: {expiry.strftime('%Y-%m-%d %H:%M:%S')}\n")
        else:
            new_lines.append(line)

    new_lines.append(f"\n# OAuth token auto-refreshed {now.strftime('%Y-%m-%d %H:%M:%S')}\n")

    with open("credentials.txt", "w") as f:
        f.writelines(new_lines)

    log.info(f"Token saved to credentials.txt (expires {expiry.strftime('%Y-%m-%d %H:%M:%S')})")


if __name__ == "__main__":
    success = refresh_token()
    if not success:
        exit(1)
