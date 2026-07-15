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

## 4. First-run authentication (one-time)

- **eBay OAuth** — if you don't yet have valid tokens, run once:
  ```bash
  python ai_ebay_get_oauth_token.py     # browser-based, seeds credentials.txt
  ```
  Afterwards `ai_ebay_refresh_oauth_token.py` (airotate Step 0) keeps it fresh.
- **Playwright eBay session** — the first browser task will prompt an eBay login;
  the session is saved to `.playwright_profile/` and reused thereafter. (Auto-login
  fills credentials from `credentials.txt`.)

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
