import os
import requests
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_message(text):
    """Send a message to Telegram"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("  ✅ Telegram message sent")
        else:
            print(f"  ❌ Telegram error: {response.text}")
    except Exception as e:
        print(f"  ❌ Telegram exception: {e}")


def format_swing_alert(signals, total_stocks):
    """Format the full swing scan report"""
    date_str = datetime.now().strftime("%d %B %Y | %I:%M %p")

    lines = []
    lines.append(f"🔍 <b>SWING SCAN — {date_str}</b>\n")

    if not signals:
        lines.append("❌ <b>No clean setups found today.</b>")
        lines.append(f"\n📊 {total_stocks} stocks scanned — WAIT for better conditions.")
        return "\n".join(lines)

    lines.append(f"✅ <b>{len(signals)} SETUP(S) FOUND:</b>\n")

    for i, s in enumerate(signals, 1):
        lines.append(f"<b>{i}. {s['symbol']} — Score {s['score']}/10 🟢</b>")
        lines.append(f"   Entry: ₹{s['entry']}")
        lines.append(f"   Stop Loss: ₹{s['sl']} ({s['sl_pct']}% risk)")
        lines.append(f"   Target: ₹{s['target']} ({s['target_pct']}% gain)")
        lines.append(f"   R/R: 1:{s['rr']} ✅")
        lines.append(f"   Hold: {s['hold_days']}")
        lines.append(f"   Qty: {s['qty']} shares | Capital: ₹{int(s['capital_needed'])}")
        lines.append(f"   Max Loss: ₹{int(s['max_loss'])} | Max Profit: ₹{int(s['max_profit'])}")
        lines.append(f"   Reason: {' + '.join(s['reasons'])}\n")

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
    # Simulate the ONGC signal
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
        }
    ]

    print("Formatted message preview:\n")
    print(format_swing_alert(test_signals, 48))
    print("\n" + "="*50)
    send_swing_alert(test_signals, 48)