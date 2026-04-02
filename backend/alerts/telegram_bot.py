import os
import html
import requests
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Support multiple chat IDs — comma separated in .env
# Example: TELEGRAM_CHAT_IDS=123456789,987654321
CHAT_IDS = [cid.strip() for cid in os.getenv("TELEGRAM_CHAT_IDS", "").split(",") if cid.strip()]

# Fallback to single CHAT_ID if TELEGRAM_CHAT_IDS not set
if not CHAT_IDS:
    single = os.getenv("TELEGRAM_CHAT_ID", "")
    if single:
        CHAT_IDS = [single]


def send_message(text):
    """Send a message to all configured Telegram chat IDs"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    for chat_id in CHAT_IDS:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
        }
        try:
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                print(f"  ✅ Telegram message sent → {chat_id}")
            else:
                print(f"  ❌ Telegram error for {chat_id}: {response.text}")
        except Exception as e:
            print(f"  ❌ Telegram exception for {chat_id}: {e}")


def format_swing_alert(signals, total_stocks):
    """Format the full swing scan report"""
    date_str = datetime.now().strftime("%d %B %Y | %I:%M %p")

    lines = []
    lines.append(f"🔍 <b>SWING SCAN — {date_str}</b>\n")

    if not signals:
        lines.append("❌ <b>No clean setups found today.</b>")
        lines.append(f"\n📊 {total_stocks} stocks scanned — WAIT for better conditions.")
        return "\n".join(lines)

    bullish = [s for s in signals if s["trend"].lower() == "bullish"]
    bearish = [s for s in signals if s["trend"].lower() == "bearish"]

    if bullish:
        lines.append(f"🟢 <b>BULLISH SETUPS — {len(bullish)} found:</b>\n")
        for i, s in enumerate(bullish, 1):
            reasons = ' + '.join(html.escape(r) for r in s['reasons'])
            lines.append(f"<b>{i}. {s['symbol']} — Score {s['score']}/10</b>")
            lines.append(f"   Entry: ₹{s['entry']}")
            lines.append(f"   Stop Loss: ₹{s['sl']} ({s['sl_pct']}% risk)")
            lines.append(f"   Target: ₹{s['target']} ({s['target_pct']}% gain)")
            lines.append(f"   R/R: 1:{s['rr']} ✅")
            lines.append(f"   Hold: {s.get('hold_days', '5-8 days')}")
            lines.append(f"   Qty: {s.get('qty', '-')} shares | Capital: ₹{int(s.get('capital_needed', 0))}")
            lines.append(f"   Max Loss: ₹{int(s.get('max_loss', 0))} | Max Profit: ₹{int(s.get('max_profit', 0))}")
            lines.append(f"   Reason: {reasons}\n")

    if bearish:
        lines.append(f"🔴 <b>BEARISH SETUPS (SHORT) — {len(bearish)} found:</b>\n")
        for i, s in enumerate(bearish, 1):
            reasons = ' + '.join(html.escape(r) for r in s['reasons'])
            lines.append(f"<b>{i}. {s['symbol']} — Score {s['score']}/10</b>")
            lines.append(f"   Short Entry: ₹{s['entry']}")
            lines.append(f"   Stop Loss: ₹{s['sl']} ({s['sl_pct']}% risk)")
            lines.append(f"   Target: ₹{s['target']} ({s['target_pct']}% gain)")
            lines.append(f"   R/R: 1:{s['rr']} ✅")
            lines.append(f"   Hold: {s.get('hold_days', '5-8 days')}")
            lines.append(f"   Qty: {s.get('qty', '-')} shares | Capital: ₹{int(s.get('capital_needed', 0))}")
            lines.append(f"   Max Loss: ₹{int(s.get('max_loss', 0))} | Max Profit: ₹{int(s.get('max_profit', 0))}")
            lines.append(f"   Reason: {reasons}\n")

    rejected = total_stocks - len(signals)
    lines.append(f"❌ {rejected} stocks — No clean setup. WAIT.")
    lines.append(f"\n📊 Scanned: {total_stocks} Nifty 50 stocks")

    return "\n".join(lines)


def send_swing_alert(signals, total_stocks):
    """Send the swing scan report to Telegram"""
    message = format_swing_alert(signals, total_stocks)
    print("\nSending Telegram alert...")
    send_message(message)


# Quick test
if __name__ == "__main__":
    test_signals = [
        {
            "symbol": "ONGC",
            "score": 7.5,
            "entry": 284.6,
            "sl": 274.2,
            "target": 305.6,
            "sl_pct": 3.7,
            "target_pct": 7.4,
            "rr": 2.0,
            "rsi": 65.3,
            "adx": 32.2,
            "vol_ratio": 1.51,
            "trend": "bullish",
            "reasons": ["EMA20 > EMA50", "ADX 32.2", "Volume 1.5x average", "no key level nearby"],
            "hold_days": "5-8 days",
            "qty": 35,
            "capital_needed": 9961.0,
            "max_loss": 364.0,
            "max_profit": 735.0,
        },
        {
            "symbol": "HDFCBANK",
            "score": 7.8,
            "entry": 1685.0,
            "sl": 1720.0,
            "target": 1615.0,
            "sl_pct": 2.1,
            "target_pct": 4.2,
            "rr": 2.0,
            "rsi": 55.0,
            "adx": 47.7,
            "vol_ratio": 1.80,
            "trend": "bearish",
            "reasons": ["EMA20 < EMA50 (bearish trend)", "ADX 47.7", "Volume 1.8x average", "at key resistance"],
            "hold_days": "3-5 days",
            "qty": 10,
            "capital_needed": 16850.0,
            "max_loss": 350.0,
            "max_profit": 700.0,
        }
    ]

    print("Formatted message preview:\n")
    print(format_swing_alert(test_signals, 48))
    print("\n" + "="*50)
    send_swing_alert(test_signals, 48)