"""
telegram_notify.py
------------------
Reads scanner output and sends a formatted Telegram message.

Now uses HTML mode (safer than Markdown)
"""

import os
import sys
import requests
from datetime import datetime


BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

CHAT_IDS = [
    cid.strip()
    for cid in os.environ["TELEGRAM_CHAT_IDS"].split(",")
    if cid.strip()
]


def send_message(text: str) -> None:
    """Send the same message to every chat ID."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    for chat_id in CHAT_IDS:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",   # ✅ switched to HTML
            "disable_web_page_preview": True,
        }

        resp = requests.post(url, json=payload, timeout=15)

        # 🔍 Debug response (important)
        print(f"Telegram response: {resp.status_code} - {resp.text}")

        try:
            resp.raise_for_status()
            print(f"✅ Sent to chat_id {chat_id}")
        except Exception as e:
            print(f"❌ Failed to send to {chat_id}: {e}")


def escape_html(text: str) -> str:
    """Escape special HTML characters."""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )


def format_message(raw: str) -> str:
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    now = datetime.now().strftime("%d %b %Y  %H:%M IST")

    if not lines:
        return f"📊 <b>Share-Lens Scanner</b> — {now}\n\nNo stocks found."

    # Escape each line to avoid HTML issues
    safe_lines = [escape_html(line) for line in lines]

    ticker_lines = "\n".join(f"• <code>{t}</code>" for t in safe_lines)

    return (
        f"📊 <b>Share-Lens Scanner</b> — {now}\n"
        f"{'─' * 30}\n"
        f"{ticker_lines}\n"
        f"{'─' * 30}\n"
        f"<b>{len(lines)} stock(s) flagged</b>"
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