"""
telegram_notify.py
------------------
Reads a plain list of stock tickers from scanner.py output
and sends a formatted Telegram message to one or more chat IDs.

Expected scanner.py output (one ticker per line):
    RELIANCE
    TCS
    HDFCBANK
    INFY
"""

import os
import sys
import requests
from datetime import datetime


BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

# TELEGRAM_CHAT_IDS supports multiple IDs, comma-separated
# e.g. "123456789,-1001234567890"
CHAT_IDS = [
    cid.strip()
    for cid in os.environ["TELEGRAM_CHAT_IDS"].split(",")
    if cid.strip()
]


def send_message(text: str) -> None:
    """Send the same message to every chat ID."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    for chat_id in CHAT_IDS:
        resp = requests.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }, timeout=15)
        resp.raise_for_status()
        print(f"✅ Sent to chat_id {chat_id} (HTTP {resp.status_code})")


def format_message(raw: str) -> str:
    tickers = [line.strip().upper() for line in raw.splitlines() if line.strip()]
    now     = datetime.now().strftime("%d %b %Y  %H:%M IST")

    if not tickers:
        return f"📊 *Share-Lens Scanner* — {now}\n\n_No stocks found in this scan._"

    ticker_lines = "\n".join(f"• `{t}`" for t in tickers)

    return (
        f"📊 *Share-Lens Scanner* — {now}\n"
        f"{'─' * 30}\n"
        f"{ticker_lines}\n"
        f"{'─' * 30}\n"
        f"_{len(tickers)} stock(s) flagged_"
    )


def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            raw = f.read()
    else:
        raw = sys.stdin.read()

    message = format_message(raw)
    print("Sending message:\n", message)
    send_message(message)


if __name__ == "__main__":
    main()