"""
Central configuration & secrets loader.

Secrets are read from environment variables, optionally seeded from a local
`.env` file (which is gitignored and NEVER committed). This module contains NO
real secret values -- only variable names and safe defaults. See `.env.example`
for the variables to set.

Usage:
    from config import PY_ACCOUNT_ID, PY_API_KEY
    # or, to fail fast when a required secret is missing:
    from config import require
    key = require("PY_API_KEY")
"""

import os
from pathlib import Path


def _load_dotenv():
    """Minimal .env loader (no third-party dependency). Lines of the form
    KEY=value; `#` comments and blanks ignored. Existing real environment
    variables always win over the .env file."""
    env_path = Path(__file__).with_name(".env")
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def _read_credentials_txt():
    """Parse the gitignored credentials.txt (KEY=value lines) into a dict."""
    out = {}
    path = Path(__file__).with_name("credentials.txt")
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        out[key.strip()] = val.strip()
    return out


_load_dotenv()
_CREDS = _read_credentials_txt()

# --- eBay login (Selenium/Playwright) & Gmail (SMTP fallback) ---------------
EBAY_USER = os.environ.get("EBAY_USER") or _CREDS.get("ebay_user", "")
EBAY_PASS = os.environ.get("EBAY_PASS") or _CREDS.get("ebay_pass", "")
GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS") or _CREDS.get("gmail_address", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD") or _CREDS.get("gmail_app_password", "")

# --- PriceYak ---------------------------------------------------------------
PY_ACCOUNT_ID = os.environ.get("PY_ACCOUNT_ID", "")
PY_API_KEY = os.environ.get("PY_API_KEY", "")

# --- OpenAI -----------------------------------------------------------------
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# --- eBay (Trading / OAuth app credentials) ---------------------------------
# Note: per-call eBay auth tokens live in credentials.txt (also gitignored);
# this is only the developer app Cert ID used by a couple of REST helpers.
EBAY_CERT_ID = os.environ.get("EBAY_CERT_ID", "")


def require(name):
    """Return the named secret, or raise a clear error if it is unset."""
    val = os.environ.get(name) or globals().get(name)
    if not val:
        raise RuntimeError(
            f"Missing required secret {name!r}. Set it in your environment or "
            f"in a local .env file (see .env.example)."
        )
    return val
