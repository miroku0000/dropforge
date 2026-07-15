"""
Lightweight push notifications + local log for the automation pipeline.

Channels are all optional -- with none configured it just logs locally, so
nothing breaks. Configure any of these in notify_config.txt (key=value lines):

    ntfy_topic=my-secret-ebay-topic       # install the ntfy app, subscribe to
                                           # this topic -> instant phone push,
                                           # no account. (or set env NTFY_TOPIC)
    ntfy_server=https://ntfy.sh           # optional, this is the default
    telegram_token=123:ABC                # optional Telegram bot
    telegram_chat_id=987654321

Usage:
    from notify import send
    send("airotate done", "33 ok, 2 warnings", priority="default", tags="package")
"""

import os
import logging

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("ebay_ads_automation.log", encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger(__name__)

CONFIG_FILE = "notify_config.txt"
DEFAULT_NTFY_SERVER = "https://ntfy.sh"


def _config():
    cfg = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    cfg[k.strip()] = v.strip()
    return cfg


def send(title, message, priority="default", tags=None):
    """Push `message` to every configured channel; always logs locally.
    Returns True if at least one push channel accepted it."""
    cfg = _config()
    sent = False

    topic = os.environ.get("NTFY_TOPIC") or cfg.get("ntfy_topic")
    if topic:
        server = cfg.get("ntfy_server", DEFAULT_NTFY_SERVER).rstrip("/")
        url = topic if topic.startswith("http") else f"{server}/{topic}"
        headers = {"Title": _ascii(title), "Priority": priority}
        if tags:
            headers["Tags"] = tags
        try:
            r = requests.post(url, data=message.encode("utf-8"), headers=headers, timeout=15)
            if r.status_code < 300:
                sent = True
            else:
                log.warning(f"ntfy returned {r.status_code}: {r.text[:120]}")
        except Exception as e:
            log.warning(f"ntfy push failed: {e}")

    tok, chat = cfg.get("telegram_token"), cfg.get("telegram_chat_id")
    if tok and chat:
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{tok}/sendMessage",
                json={"chat_id": chat, "text": f"*{title}*\n{message}", "parse_mode": "Markdown"},
                timeout=15,
            )
            if r.status_code < 300:
                sent = True
        except Exception as e:
            log.warning(f"telegram push failed: {e}")

    first = (message or "").splitlines()[0] if message else ""
    log.info(f"[NOTIFY] {title} :: {first}")
    if not sent:
        log.info("(no push channel delivered; set ntfy_topic in notify_config.txt to get phone push)")
    return sent


def _ascii(s):
    """ntfy headers must be latin-1 safe; strip non-ascii from the title."""
    return (s or "").encode("ascii", "ignore").decode("ascii") or "notification"


if __name__ == "__main__":
    import sys
    t = sys.argv[1] if len(sys.argv) > 1 else "test"
    m = sys.argv[2] if len(sys.argv) > 2 else "notify.py test message"
    print("delivered to a push channel:" , send(t, m))
