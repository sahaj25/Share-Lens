"""
telegram_notify.py
------------------
Reads scanner output and sends formatted Telegram messages.
Automatically splits large ticker lists into multiple messages.
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

MAX_CHARS = 3800  # Telegram limit is 4096; keep buffer


def send_message(text: str) -> None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    for chat_id in CHAT_IDS:
        resp = requests.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }, timeout=15)
        print(f"Telegram response: {resp.status_code} - {resp.text[:120]}")
        try:
            resp.raise_for_status()
            print(f"✅ Sent to chat_id {chat_id}")
        except Exception as e:
            print(f"❌ Failed to send to {chat_id}: {e}")


def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def chunk_tickers(tickers: list, max_chars: int) -> list[list]:
    """Split tickers into groups that each fit within max_chars."""
    chunks, current, current_len = [], [], 0
    for t in tickers:
        line = f"• <code>{escape_html(t)}</code>\n"
        if current_len + len(line) > max_chars and current:
            chunks.append(current)
            current, current_len = [], 0
        current.append(t)
        current_len += len(line)
    if current:
        chunks.append(current)
    return chunks


def format_chunk(tickers: list, part: int, total_parts: int,
                 total_tickers: int, now: str) -> str:
    ticker_lines = "\n".join(f"• <code>{escape_html(t)}</code>" for t in tickers)
    part_label = f"  ({part}/{total_parts})" if total_parts > 1 else ""

    return (
        f"📊 <b>Share-Lens Scanner</b>{part_label} — {now}\n"
        f"{'─' * 30}\n"
        f"{ticker_lines}\n"
        f"{'─' * 30}\n"
        f"<b>{total_tickers} stock(s) flagged</b>"
    )


def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            raw = f.read()
    else:
        raw = sys.stdin.read()

    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    now   = datetime.now().strftime("%d %b %Y  %H:%M IST")

    if not lines:
        send_message(f"📊 <b>Share-Lens Scanner</b> — {now}\n\nNo stocks found.")
        return

    chunks = chunk_tickers(lines, MAX_CHARS)
    total  = len(chunks)
    print(f"Sending {len(lines)} tickers in {total} message(s)...")

    for i, chunk in enumerate(chunks, 1):
        msg = format_chunk(chunk, i, total, len(lines), now)
        print(f"\n--- Message {i}/{total} ---\n{msg[:200]}...")
        send_message(msg)


if __name__ == "__main__":
    main()