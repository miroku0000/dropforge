# eBay Traffic Report Scripts

This directory contains two scripts for downloading eBay traffic/performance data:

## 1. download_ebay_traffic_report_tradingapi.py (WORKING)

**Status:** ✓ Working with existing credentials

Uses the Trading API `GetSellerList` to fetch listing data including:
- ItemID, Title, SKU
- Hit Count (views/impressions) - Note: May return 0 due to API limitations
- Watch Count
- Quantity Sold
- Listing dates and URLs

**Usage:**
```bash
python download_ebay_traffic_report_tradingapi.py
```

**Output:**
- CSV file: `../data/ebay_traffic_data_YYYYMMDD_HHMMSS.csv`
- JSON file: `../data/ebay_traffic_data_YYYYMMDD_HHMMSS.json`

**Limitations:**
- HitCount may not be available through GetSellerList
- Limited to 30 days of listing data
- Does not provide detailed analytics like the Analytics API

---

## 2. download_ebay_traffic_report.py (REQUIRES OAUTH)

**Status:** ⚠ Requires OAuth 2.0 user token with Analytics API scope

This script uses the official eBay Analytics API to get the same traffic data available in Seller Hub > Performance > Traffic page.

**Metrics Available:**
- CLICK_THROUGH_RATE
- LISTING_IMPRESSION_SEARCH_RESULTS_PAGE
- LISTING_IMPRESSION_STORE
- LISTING_IMPRESSION_TOTAL
- LISTING_VIEWS_SOURCE_DIRECT
- LISTING_VIEWS_SOURCE_OFF_EBAY
- LISTING_VIEWS_SOURCE_OTHER_EBAY
- LISTING_VIEWS_TOTAL
- SALES_CONVERSION_RATE
- TRANSACTION

**Requirements:**

To use this script, you need an OAuth 2.0 token with the Analytics API scope:

### Step 1: Generate OAuth Token in eBay Developer Portal

1. Go to: https://developer.ebay.com/my/keys
2. Click on your application (e.g., "AIItemSp")
3. Click "User Tokens" link next to your App ID
4. In the OAuth scopes section, select:
   - `https://api.ebay.com/oauth/api_scope/sell.analytics.readonly`
5. Click "Get a Token from eBay via Your Application"
6. Sign in with your eBay seller account
7. Grant access to the application
8. Copy the generated **Refresh Token** (not the Access Token)

### Step 2: Update credentials.txt

Add a new line to `credentials.txt`:
```
oauth_refresh_token=YOUR_REFRESH_TOKEN_HERE
```

OR replace the existing `token=` line with:
```
token=YOUR_REFRESH_TOKEN_HERE
```

### Step 3: Run the Script

```bash
python download_ebay_traffic_report.py
```

**Output:**
- CSV file: `../data/ebay_traffic_report_YYYYMMDD_HHMMSS.csv`
- JSON file: `../data/ebay_traffic_report_YYYYMMDD_HHMMSS.json`

---

## Comparison

| Feature | Trading API Script | Analytics API Script |
|---------|-------------------|---------------------|
| Authentication | Auth'n'Auth token (existing) | OAuth 2.0 required |
| Setup | ✓ Works immediately | Requires token generation |
| Hit Count | Limited/0 | ✓ Full metrics |
| Impressions by Source | ✗ | ✓ Yes |
| Conversion Rate | Calculate manually | ✓ Provided |
| Date Range | 30 days | Up to 90 days |
| Dimension | Listing-level only | By DAY or by LISTING |

---

## Troubleshooting

### "invalid_grant" error when running Analytics API script

This means your token is either:
- An Auth'n'Auth token (not OAuth 2.0)
- An OAuth token without the Analytics scope
- An expired OAuth token

**Solution:** Follow the OAuth token generation steps above.

### HitCount returns 0 in Trading API script

The Trading API may not return HitCount through GetSellerList for all accounts or listing types. This is a known limitation.

**Alternative:** Use the Analytics API script (requires OAuth setup).

---

## Recommendation

For production use and accurate traffic data, use the **Analytics API script** (`download_ebay_traffic_report.py`) after setting up OAuth 2.0 tokens. The one-time setup is worth it for access to comprehensive traffic metrics.

For quick listing exports without traffic details, the **Trading API script** works with your existing credentials.