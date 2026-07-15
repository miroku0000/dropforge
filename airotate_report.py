"""
Summarize an airotate run and push a digest notification.

Reads the captured console log of an airotate run (produced by run_airotate.bat,
which tees airotate's output to logs\airotate_<ts>.log). Airotate already prints
a consistent structure we can parse:
    [STEP <id>] <description>      -> a step starts
    [WARNING] <msg>                -> that step reported a problem (errorlevel)
plus python tracebacks (uncaught crashes) and per-script summary lines.

It builds a per-step OK / WARN / FAIL digest with key metrics (terms added,
listings ended, offers, etc.), writes logs\run_summary_<ts>.json, and pushes the
digest via notify.send so a silent failure can't hide.

Usage:
    python airotate_report.py logs\airotate_20260612_154500.log
"""

import os
import re
import sys
import json
import glob
from datetime import datetime

from notify import send

# Key metrics: (label, compiled regex with one int group, aggregation)
METRICS = [
    ("search terms added", re.compile(r"Added (\d+) new search term"), "sum"),
    ("OOS listings ended", re.compile(r"bulk_delist accepted (\d+)"), "sum"),
    ("listings ended (sweep)", re.compile(r"Ended (\d+) listing\(s\)"), "sum"),
    ("IRC flagged", re.compile(r"Scraped (\d+) flagged listing"), "last"),
    ("ASINs relisted", re.compile(r"Submitting (\d+) ASINs to PriceYak"), "last"),
    ("ASINs scraped", re.compile(r"Total ASINs extracted: (\d+)"), "last"),
]

STEP_RE = re.compile(r"\[STEP ([^\]]+)\]\s*(.*)")
WARN_RE = re.compile(r"\[WARNING\]\s*(.*)", re.IGNORECASE)
ERR_RE = re.compile(r"^(Traceback \(most recent call last\)|[A-Za-z_][\w.]*(Error|Exception): )")
TIME_RE = re.compile(r"(Started|Finished) at:\s*(.*)")


def _read_text(path):
    """Read the run log regardless of encoding. PowerShell Tee-Object writes
    UTF-16 by default, so a naive utf-8 read yields NUL-interleaved garbage that
    matches nothing (and would falsely report 'pipeline didn't start')."""
    with open(path, "rb") as f:
        raw = f.read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", errors="ignore")
    if raw[:3] == b"\xef\xbb\xbf":
        return raw.decode("utf-8-sig", errors="ignore")
    if raw.count(b"\x00") > len(raw) // 4:          # UTF-16 without BOM
        return raw.decode("utf-16", errors="ignore")
    return raw.decode("utf-8", errors="ignore")


def parse(path):
    steps, cur, metrics, times = [], None, {}, {}
    for line in _read_text(path).splitlines():
        ms = STEP_RE.search(line)
        if ms:
            cur = {"id": ms.group(1).strip(), "desc": ms.group(2).strip(),
                   "warnings": [], "errors": []}
            steps.append(cur)
            continue

        mw = WARN_RE.search(line)
        if mw and not mw.group(1).lower().startswith(("min ratings", "no push")):
            (cur or _orphan(steps))["warnings"].append(mw.group(1).strip())
            continue

        if ERR_RE.search(line.strip()) and cur is not None and len(cur["errors"]) < 3:
            cur["errors"].append(line.strip()[:120])

        mt = TIME_RE.search(line)
        if mt:
            times[mt.group(1).lower()] = mt.group(2).strip()

        for label, rx, agg in METRICS:
            m = rx.search(line)
            if m:
                val = int(m.group(1))
                metrics[label] = metrics.get(label, 0) + val if agg == "sum" else val
    return steps, metrics, times


def _orphan(steps):
    if not steps or steps[-1]["id"] != "(preamble)":
        steps.append({"id": "(preamble)", "desc": "", "warnings": [], "errors": []})
    return steps[-1]


def build_digest(steps, metrics, times):
    issues = [s for s in steps if s["warnings"] or s["errors"]]
    failed = [s for s in issues if s["errors"]]
    n_ok = len(steps) - len(issues)

    if not steps:
        title = "airotate: NO OUTPUT"
        body = "No steps were parsed from the run log -- the pipeline may not have started."
        return title, body, "urgent", {"steps": 0, "ok": 0, "issues": 0, "failed": 0}

    if failed:
        title = f"airotate: {len(failed)} FAILED, {len(issues) - len(failed)} warn"
        prio = "high"
    elif issues:
        title = f"airotate: {len(issues)} warning(s)"
        prio = "default"
    else:
        title = "airotate: all clear"
        prio = "low"

    lines = [f"{len(steps)} steps -- {n_ok} ok, {len(issues)} with issues"]
    if times.get("started") and times.get("finished"):
        lines.append(f"{times['started']}  ->  {times['finished']}")
    for s in issues:
        flag = "X" if s["errors"] else "!"
        detail = (s["errors"][0] if s["errors"] else s["warnings"][0])[:90]
        lines.append(f"{flag} [{s['id']}] {detail}")
    if metrics:
        lines.append("")
        lines.append(" | ".join(f"{k}: {v}" for k, v in metrics.items()))

    summary = {"steps": len(steps), "ok": n_ok, "issues": len(issues), "failed": len(failed)}
    return title, "\n".join(lines), prio, summary


def _listings_line():
    """Net listing change this run + eBay monthly headroom (best-effort)."""
    try:
        import check_limits
        active = check_limits.active_count()
        morning = (check_limits.load_state().get("airotate") or {}).get("count")
        net = f" ({active - morning:+d} this run)" if morning is not None else ""
        q, a = check_limits.get_ebay_headroom()        # subprocess: won't hang the report
        head = f" | eBay headroom {q} items, ${a:,.0f}" if q is not None else ""
        return f"Listings: {active} active{net}{head}"
    except Exception as e:
        return f"Listings: (unavailable: {str(e)[:50]})"


def main():
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        logs = glob.glob(os.path.join("logs", "airotate_*.log"))
        path = max(logs, key=os.path.getmtime) if logs else None
    if not path or not os.path.exists(path):
        print("Usage: python airotate_report.py <run-log>  (no log found)")
        send("airotate: NO LOG", "airotate_report could not find a run log to summarize.", priority="high")
        return

    steps, metrics, times = parse(path)
    title, body, prio, summary = build_digest(steps, metrics, times)
    body += "\n" + _listings_line()

    print("=" * 60)
    print(title)
    print(body)
    print("=" * 60)

    os.makedirs("logs", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join("logs", f"run_summary_{ts}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"log": path, "title": title, **summary, "metrics": metrics,
                   "issues": [{"id": s["id"], "warnings": s["warnings"], "errors": s["errors"]}
                              for s in steps if s["warnings"] or s["errors"]]},
                  f, indent=2)
    print(f"Wrote {out}")

    tags = "rotating_light" if prio in ("high", "urgent") else ("warning" if "warning" in title else "white_check_mark")
    send(title, body, priority=prio, tags=tags)


if __name__ == "__main__":
    main()
