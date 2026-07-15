# Setup — fresh machine checklist

Step-by-step to get this system running on a new Windows machine.

## 1. Prerequisites

- **Python 3.10** (the codebase targets 3.10.9) — `python --version`
- **git**
- **Google Chrome** (used by the Playwright browser-automation tasks)
- Windows (paths and `.bat` scripts assume Windows; `D:\zikprocessor\src` layout)

## 2. Clone & install

```bash
git clone <your-remote-url> zikprocessor
cd zikprocessor/src
pip install -r requirements.txt
python -m playwright install chromium      # for the browser-driven tasks
```

## 3. Configure secrets (nothing here is committed)

Copy each template to its real filename and fill in values:

```bash
cp .env.example .env                         # PriceYak, OpenAI, eBay cert
cp credentials.example.txt credentials.txt   # eBay app keys, OAuth, login, Gmail
cp crawlbase_creds.example.txt crawlbase_creds.txt
```

What goes where:

| File | Holds | Notes |
|------|-------|-------|
| `.env` | `PY_ACCOUNT_ID`, `PY_API_KEY`, `OPENAI_API_KEY`, `EBAY_CERT_ID` | Loaded by `config.py`. `OPENAI_API_KEY` may instead live in your shell env. |
| `credentials.txt` | eBay `appid`/`devid`/`certid`, OAuth tokens, `ebay_user`/`ebay_pass`, `gmail_address`/`gmail_app_password` | OAuth tokens are auto-managed after first login. |
| `crawlbase_creds.txt` | Crawlbase (scraping) token | Single line. |

Sanity check the loader:

```bash
python -c "import config; print('PriceYak:', bool(config.PY_API_KEY), '| eBay login:', bool(config.EBAY_USER))"
```

## 4. Onboard your eBay store into the app (one-time)

Before the automation can call eBay on your behalf, you must register a developer
application and **authorize your seller account against it**. This is a one-time
setup per store.

### 4.1 Create the eBay Developer app (keyset)

1. Sign up at the [eBay Developers Program](https://developer.ebay.com/) with (or
   linked to) the eBay account that owns the store.
2. Create a **Production** keyset. It gives you three values:
   - **App ID (Client ID)** → `appid`
   - **Dev ID** → `devid`
   - **Cert ID (Client Secret)** → `certid`
3. Put them in `credentials.txt` (and `EBAY_CERT_ID` in `.env`):
   ```
   appid=YourApp-Name-PRD-xxxxxxxxx-xxxxxxxx
   devid=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
   certid=PRD-xxxxxxxxxxxx-xxxx-xxxx-xxxx-xxxx
   ```

### 4.2 Configure OAuth (redirect + scopes)

In the keyset's **User Tokens** settings:
- Add an accepted **redirect URI** matching the one the helper uses:
  `http://localhost:5001/oauth/callback` (see `ebay_oauth_helper.py`).
- Enable the Sell scopes the automation needs:
  `sell.inventory`, `sell.marketing`, `sell.account`, `sell.fulfillment`
  (plus analytics for the traffic reports).

### 4.3 Authorize (onboard) your store

Have the **store owner** grant the app access — this is the consent step that
"connects the store to the application" and yields the user + refresh tokens:

```bash
python ai_ebay_get_oauth_token.py     # opens the eBay Developer Portal OAuth flow,
                                      # you sign in + consent, token saved to credentials.txt
```
(Alternative: `python ebay_oauth_helper.py` runs a local redirect-based consent
flow on `localhost:5001`.)

After the first grant, **`ai_ebay_refresh_oauth_token.py`** (airotate Step 0)
keeps the token fresh automatically using the stored refresh token — no browser
needed until the refresh token itself expires (~18 months), when you re-run 4.3.

### 4.4 Link the store in PriceYak

The listings themselves are created and repriced by **PriceYak**, not this code
directly — so the same eBay store must also be connected inside your PriceYak
account (PriceYak dashboard → connect eBay account). The API key/account ID in
`.env` then let the automation drive that PriceYak account.

### 4.5 Playwright browser session

The first browser-driven task (ads/traffic reports, offers, etc.) prompts an eBay
**store-front** login; the session is saved to `.playwright_profile/` and reused.
Auto-login fills `ebay_user`/`ebay_pass` from `credentials.txt`.

## 5. Tune your targets

Edit `listing_config.bat`:

```
set MAX_LISTINGS=2580     # your store-size target
set MIN_PRICE=50          # listing / scrape price floor
```

`check_limits.py` auto-adjusts the rest against eBay headroom.

## 6. Run

```bash
run_airotate.bat                    # full daily pipeline (see AIROTATE.md)
python check_limits.py              # tune store size (run a few hours later)
python remote_control_server.py     # phone control panel at http://<PC-IP>:5000
```

## 7. Schedule (optional)

Use Windows Task Scheduler to run `run_airotate.bat` each morning and
`check_limits.py` midday. See `CLAUDE.md` for the full named-task catalog.

---

**Security reminder:** never commit `credentials.txt`, `crawlbase_creds.txt`, or
`.env` — they're gitignored for you. If credentials are ever exposed, rotate the
eBay password, Gmail app password, and PriceYak/Crawlbase/OpenAI keys.
