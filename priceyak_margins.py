"""
Manage PriceYak margin / pricer settings from the command line.

PriceYak stores its pricing config in the account object under `pricer`, a dict
keyed by source retailer (amazon, walmart, newegg, ...). Each source uses the
"range" pricer: a list of `margin_ranges` selected by the item's source cost
(`price_point` is the cost threshold), plus per-source knobs:

  margin_ranges[]     cost >= price_point uses this range's margin
    price_point         cost threshold ($) at which this range starts
    margin_fixed        flat $ added to every sale in the range
    margin_percent      % of price taken as margin (stored as a fraction: 0.25 = 25%)
  quantity_in_stock   max qty listed per item  <-- qty=2 doubles eBay $-limit burn
  margin_min          floor $ profit
  enable_sales_ranges when true, slow movers get repriced to sales_ranges margin
  sales_ranges[]      margin_percent applied by recent sales_count

Read:   GET  /v0/account/{id}                -> account.pricer
Write:  PUT  /v0/account/{id}  {"pricer": …} -> 200 (partial merge; other
        account fields and other sources are preserved). Sending the FULL
        account back returns 500, so we only ever send {"pricer": …}.

Percent flags are entered as PERCENTAGE POINTS (--percent 25 = 25% = 0.25).

Usage:
    python priceyak_margins.py show                         # all sources
    python priceyak_margins.py show --source amazon
    python priceyak_margins.py show --json

    # Change a range (select the range by its price_point):
    python priceyak_margins.py set --source amazon --price-point 25 --fixed 4.99 --percent 20

    # Drop listed quantity to 1 for a source (frees eBay $-limit headroom):
    python priceyak_margins.py set-qty --qty 1 --source amazon
    python priceyak_margins.py set-qty --qty 1 --all

    # Restore a previous config:
    python priceyak_margins.py restore --file priceyak_pricer_backups/pricer_20260810_151500.json

Writes are DRY-RUN by default. Add --yes to actually apply.
"""

import os
import sys
import json
import copy
import argparse
from datetime import datetime

import requests

from pnl_month import py_login, PY_ACCOUNT_ID

BASE = f"https://www.priceyak.com/v0/account/{PY_ACCOUNT_ID}"
BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "priceyak_pricer_backups")


# --------------------------------------------------------------------------- IO
def _headers(token):
    return {"Authorization": "Bearer " + token,
            "Accept": "*/*", "Content-Type": "application/json"}


def get_account(token):
    r = requests.get(BASE, headers=_headers(token), timeout=30)
    r.raise_for_status()
    return r.json()


def put_pricer(token, pricer):
    """Partial-merge write. Only the pricer is sent; all else is preserved."""
    r = requests.put(BASE, headers=_headers(token), json={"pricer": pricer}, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"PUT failed {r.status_code}: {r.text[:300]}")
    return r.json()


def backup_pricer(pricer):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(BACKUP_DIR, f"pricer_{stamp}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(pricer, f, indent=2)
    return path


# ---------------------------------------------------------------------- helpers
def source_names(pricer):
    """Real source keys (skip the router's own 'name' field)."""
    return sorted(k for k, v in pricer.items() if isinstance(v, dict))


def find_range(src_cfg, price_point):
    ranges = src_cfg.get("margin_ranges") or []
    hits = [r for r in ranges if float(r.get("price_point", -1)) == float(price_point)]
    if not hits:
        pts = ", ".join(str(r.get("price_point")) for r in ranges)
        raise SystemExit(f"No margin range at price_point={price_point}. Available: {pts}")
    if len(hits) > 1:
        raise SystemExit(f"Ambiguous: {len(hits)} ranges at price_point={price_point}.")
    return hits[0]


def pct(fraction):
    return f"{fraction * 100:g}%"


# ----------------------------------------------------------------------- render
def show_source(name, cfg):
    print(f"  {name}")
    q = cfg.get("quantity_in_stock")
    flag = "  <-- 2x $-limit burn" if q == 2 else ""
    print(f"      quantity_in_stock : {q}{flag}")
    print(f"      margin_min        : ${cfg.get('margin_min', 0)}")
    print(f"      ebay_fee_assumed  : {pct(cfg.get('internal_ebay_fee_percent', 0))}   "
          f"ao_fee ${cfg.get('internal_ao_fee', 0)} (included: {cfg.get('include_ao_fee', False)})")
    print(f"      margin ranges (by source cost):")
    print(f"        {'cost >=':>9}   {'+fixed':>8}   {'+percent':>8}")
    for r in sorted(cfg.get("margin_ranges") or [], key=lambda x: x.get("price_point", 0)):
        print(f"        {('$'+str(r.get('price_point'))):>9}   "
              f"{('$'+format(r.get('margin_fixed', 0), '.2f')):>8}   "
              f"{pct(r.get('margin_percent', 0)):>8}")
    if cfg.get("enable_sales_ranges"):
        sr = cfg.get("sales_ranges") or []
        pretty = "; ".join(f">={s.get('sales_count')} sales -> {pct(s.get('margin_percent',0))}" for s in sr)
        print(f"      sales-based reprice: ON  ({pretty}; look-back {cfg.get('sales_days_back')}d)")
    print()


def cmd_show(args, token):
    pricer = get_account(token)["pricer"]
    if args.json:
        if args.source:
            print(json.dumps(pricer[args.source], indent=2))
        else:
            print(json.dumps(pricer, indent=2))
        return
    print("=" * 60)
    print(f"  PriceYak pricer  (account {PY_ACCOUNT_ID})")
    print("=" * 60)
    names = [args.source] if args.source else source_names(pricer)
    for n in names:
        if n not in pricer:
            raise SystemExit(f"Unknown source '{n}'. Known: {', '.join(source_names(pricer))}")
        show_source(n, pricer[n])


# ------------------------------------------------------------------------- edit
def _apply_and_write(token, pricer, changes, dry_run):
    """changes: list of (label, path-desc, old, new) already applied to `pricer`."""
    print("Planned changes:")
    for label, old, new in changes:
        print(f"  {label}: {old}  ->  {new}")
    if dry_run:
        print("\nDRY-RUN -- nothing written. Re-run with --yes to apply.")
        return
    path = backup_pricer(get_account(token)["pricer"])  # backup CURRENT live state
    print(f"\nBacked up current pricer -> {path}")
    put_pricer(token, pricer)
    print("Applied. New state:")
    show_source_changed(token, changes)


def show_source_changed(token, changes):
    pricer = get_account(token)["pricer"]
    shown = set()
    for label, _o, _n in changes:
        src = label.split("/")[0].strip()
        if src in pricer and src not in shown:
            show_source(src, pricer[src])
            shown.add(src)


def cmd_set(args, token):
    pricer = get_account(token)["pricer"]
    if args.source not in pricer:
        raise SystemExit(f"Unknown source '{args.source}'. Known: {', '.join(source_names(pricer))}")
    cfg = pricer[args.source]
    changes = []

    # Range-level edits require --price-point
    if args.fixed is not None or args.percent is not None:
        if args.price_point is None:
            raise SystemExit("--fixed/--percent require --price-point to pick the range.")
        rng = find_range(cfg, args.price_point)
        if args.fixed is not None:
            changes.append((f"{args.source}/pp{args.price_point} margin_fixed",
                            f"${rng.get('margin_fixed'):.2f}", f"${args.fixed:.2f}"))
            rng["margin_fixed"] = round(args.fixed, 2)
        if args.percent is not None:
            frac = args.percent / 100.0
            changes.append((f"{args.source}/pp{args.price_point} margin_percent",
                            pct(rng.get('margin_percent', 0)), pct(frac)))
            rng["margin_percent"] = frac

    if args.qty is not None:
        changes.append((f"{args.source}/quantity_in_stock", cfg.get("quantity_in_stock"), args.qty))
        cfg["quantity_in_stock"] = args.qty
    if args.min_margin is not None:
        changes.append((f"{args.source}/margin_min", f"${cfg.get('margin_min', 0)}", f"${args.min_margin}"))
        cfg["margin_min"] = args.min_margin
    if args.sales_margin is not None:
        frac = args.sales_margin / 100.0
        sr = cfg.get("sales_ranges") or [{}]
        old = pct(sr[0].get("margin_percent", 0))
        sr[0]["margin_percent"] = frac
        cfg["sales_ranges"] = sr
        changes.append((f"{args.source}/sales_ranges[0] margin_percent", old, pct(frac)))

    if not changes:
        raise SystemExit("Nothing to change. Pass --fixed/--percent (+--price-point), --qty, --min-margin, or --sales-margin.")
    _apply_and_write(token, pricer, changes, args.dry_run)


def cmd_set_qty(args, token):
    pricer = get_account(token)["pricer"]
    if args.all:
        targets = source_names(pricer)
    elif args.source:
        if args.source not in pricer:
            raise SystemExit(f"Unknown source '{args.source}'. Known: {', '.join(source_names(pricer))}")
        targets = [args.source]
    else:
        raise SystemExit("Pass --source NAME or --all.")
    changes = []
    for n in targets:
        cur = pricer[n].get("quantity_in_stock")
        if cur != args.qty:
            changes.append((f"{n}/quantity_in_stock", cur, args.qty))
            pricer[n]["quantity_in_stock"] = args.qty
    if not changes:
        print(f"All targeted sources already at quantity_in_stock={args.qty}. Nothing to do.")
        return
    _apply_and_write(token, pricer, changes, args.dry_run)


def cmd_restore(args, token):
    with open(args.file, encoding="utf-8") as f:
        pricer = json.load(f)
    if not isinstance(pricer, dict) or "amazon" not in pricer:
        raise SystemExit("File does not look like a pricer dict (no 'amazon' key).")
    print(f"Restore pricer from {args.file} ({len(source_names(pricer))} sources).")
    if args.dry_run:
        print("DRY-RUN -- nothing written. Re-run with --yes to apply.")
        return
    path = backup_pricer(get_account(token)["pricer"])
    print(f"Backed up current pricer -> {path}")
    put_pricer(token, pricer)
    print("Restored.")


# ------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Manage PriceYak margin / pricer settings")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("show", help="Show current margins")
    p.add_argument("--source", help="Limit to one source (e.g. amazon)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("set", help="Change margin fields for a source")
    p.add_argument("--source", required=True)
    p.add_argument("--price-point", type=float, help="Select the margin range by its cost threshold")
    p.add_argument("--fixed", type=float, help="Set margin_fixed ($) for that range")
    p.add_argument("--percent", type=float, help="Set margin_percent for that range, in %% points (25 = 25%%)")
    p.add_argument("--qty", type=int, help="Set quantity_in_stock")
    p.add_argument("--min-margin", type=float, help="Set margin_min ($)")
    p.add_argument("--sales-margin", type=float, help="Set slow-mover sales_ranges[0] margin_percent, in %% points")
    p.add_argument("--yes", dest="dry_run", action="store_false", help="Actually apply (default is dry-run)")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", default=True)
    p.set_defaults(func=cmd_set)

    p = sub.add_parser("set-qty", help="Set quantity_in_stock for one/all sources")
    p.add_argument("--qty", type=int, required=True)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--source")
    g.add_argument("--all", action="store_true")
    p.add_argument("--yes", dest="dry_run", action="store_false")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", default=True)
    p.set_defaults(func=cmd_set_qty)

    p = sub.add_parser("restore", help="Restore a pricer backup JSON")
    p.add_argument("--file", required=True)
    p.add_argument("--yes", dest="dry_run", action="store_false")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", default=True)
    p.set_defaults(func=cmd_restore)

    args = ap.parse_args()
    token = py_login()
    args.func(args, token)


if __name__ == "__main__":
    main()
