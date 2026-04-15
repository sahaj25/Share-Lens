import sys
sys.path.append(".")

import os
import json
import time
import pyotp
import requests
from SmartApi import SmartConnect
from dotenv import load_dotenv
from datetime import datetime
from alerts.telegram_bot import send_message, BOT_TOKEN, CHAT_IDS

load_dotenv()

POSITIONS_FILE = "storage/positions.json"


# ─── Position Storage ────────────────────────────────────────────────

def load_positions():
    try:
        with open(POSITIONS_FILE, "r") as f:
            return json.load(f)
    except:
        return []


def save_positions(positions):
    with open(POSITIONS_FILE, "w") as f:
        json.dump(positions, f, indent=2)


def add_position(symbol, token, entry, sl, target, trend, qty):
    positions = load_positions()
    for p in positions:
        if p["symbol"] == symbol:
            print(f"{symbol} already in positions")
            return
    position = {
        "symbol": symbol,
        "token": token,
        "entry": entry,
        "sl": sl,
        "target": target,
        "trend": trend,
        "qty": qty,
        "added_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "status": "open"
    }
    positions.append(position)
    save_positions(positions)
    print(f"✅ Added {symbol} to positions")


def remove_position(symbol):
    positions = load_positions()
    positions = [p for p in positions if p["symbol"] != symbol]
    save_positions(positions)


# ─── Price Fetching ──────────────────────────────────────────────────

def login():
    try:
        api = SmartConnect(api_key=os.getenv("ANGEL_API_KEY"))
        totp = pyotp.TOTP(os.getenv("ANGEL_TOTP_SECRET")).now()
        data = api.generateSession(
            os.getenv("ANGEL_CLIENT_ID"),
            os.getenv("ANGEL_PASSWORD"),
            totp
        )
        if data["status"] == False:
            return None
        return api
    except:
        return None


def get_ltp(api, symbol, token):
    try:
        data = api.ltpData("NSE", symbol, token)
        if data["status"]:
            return float(data["data"]["ltp"])
        return None
    except:
        return None


# ─── Monitor Logic ───────────────────────────────────────────────────

def check_position(position, current_price):
    entry = position["entry"]
    sl = position["sl"]
    target = position["target"]
    trend = position["trend"]

    if trend == "bullish":
        if current_price >= target:
            return "target_hit"
        if current_price <= sl:
            return "sl_hit"
        sl_distance_pct = (current_price - sl) / current_price * 100
        if sl_distance_pct <= 1.5:
            return "warning"

    elif trend == "bearish":
        if current_price <= target:
            return "target_hit"
        if current_price >= sl:
            return "sl_hit"
        sl_distance_pct = (sl - current_price) / current_price * 100
        if sl_distance_pct <= 1.5:
            return "warning"

    return "hold"


def format_target_alert(position, current_price):
    entry = position["entry"]
    qty = position["qty"]
    profit_per_share = round(abs(current_price - entry), 2)
    total_profit = round(profit_per_share * qty, 0)
    pct = round(abs(current_price - entry) / entry * 100, 2)
    return (
        f"✅ <b>TARGET HIT — {position['symbol']}</b>\n\n"
        f"Entry: ₹{entry} → Target: ₹{position['target']}\n"
        f"Current Price: ₹{current_price}\n"
        f"Profit: ₹{profit_per_share}/share | +{pct}%\n"
        f"Total Profit: ₹{total_profit} ({qty} shares)\n\n"
        f"🎯 <b>EXIT NOW</b>"
    )


def format_sl_alert(position, current_price):
    entry = position["entry"]
    qty = position["qty"]
    loss_per_share = round(abs(current_price - entry), 2)
    total_loss = round(loss_per_share * qty, 0)
    pct = round(abs(current_price - entry) / entry * 100, 2)
    return (
        f"❌ <b>STOP LOSS HIT — {position['symbol']}</b>\n\n"
        f"Entry: ₹{entry} → SL: ₹{position['sl']}\n"
        f"Current Price: ₹{current_price}\n"
        f"Loss: ₹{loss_per_share}/share | -{pct}%\n"
        f"Total Loss: ₹{total_loss} ({qty} shares)\n\n"
        f"🚨 <b>EXIT IMMEDIATELY — No averaging down</b>"
    )


def format_warning_alert(position, current_price):
    sl_distance_pct = round(abs(current_price - position["sl"]) / current_price * 100, 2)
    return (
        f"⚠️ <b>WARNING — {position['symbol']}</b>\n\n"
        f"Current Price: ₹{current_price}\n"
        f"Stop Loss: ₹{position['sl']}\n"
        f"Distance to SL: {sl_distance_pct}%\n\n"
        f"Consider early exit to reduce loss."
    )


def format_status_update(position, current_price):
    entry = position["entry"]
    pnl = round((current_price - entry) / entry * 100, 2)
    direction = "📈" if current_price > entry else "📉"
    sign = "+" if pnl > 0 else ""
    return (
        f"{direction} <b>{position['symbol']}</b> | "
        f"Entry ₹{entry} | Now ₹{current_price} | "
        f"{sign}{pnl}%"
    )


# ─── Telegram Reply Listener ─────────────────────────────────────────

def wait_for_telegram_reply(timeout=120):
    """Poll Telegram for a new message. Returns text or None on timeout."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"

    # Get current last update_id to ignore old messages
    try:
        resp = requests.get(url, params={"limit": 1, "offset": -1}, timeout=10)
        data = resp.json()
        last_update_id = None
        if data["result"]:
            last_update_id = data["result"][-1]["update_id"]
    except:
        last_update_id = None

    print(f"Waiting for Telegram reply (timeout: {timeout}s)...")
    start = time.time()

    while time.time() - start < timeout:
        try:
            params = {"timeout": 10, "limit": 1}
            if last_update_id:
                params["offset"] = last_update_id + 1

            resp = requests.get(url, params=params, timeout=15)
            data = resp.json()

            if data["result"]:
                update = data["result"][-1]
                last_update_id = update["update_id"]
                text = update.get("message", {}).get("text", "").strip()
                if text:
                    print(f"Received: {text}")
                    return text

        except Exception as e:
            print(f"Polling error: {e}")

        time.sleep(3)

    print("Timeout — no reply received.")
    return None


# ─── Ask Trades via Telegram + Auto Start Monitor ────────────────────

def ask_trades_via_telegram(signals, stock_universe):
    """Send signal list to Telegram, wait for reply, add positions, start monitor"""

    # Format question message
    lines = []
    lines.append("📋 <b>WHICH TRADES ARE YOU TAKING?</b>")
    lines.append("Reply with numbers e.g. <b>1,3,5</b> or <b>0</b> to skip\n")

    for i, s in enumerate(signals, 1):
        direction = "🟢 BULL" if s["trend"] == "bullish" else "🔴 BEAR"
        lines.append(
            f"{i}. {direction} <b>{s['symbol']}</b> | "
            f"Entry ₹{s['entry']} | SL ₹{s['sl']} | "
            f"Target ₹{s['target']} | Score {s['score']}/10"
        )

    lines.append("\n⏳ Waiting for your reply (2 min timeout)...")
    send_message("\n".join(lines))

    # Wait for reply
    reply = wait_for_telegram_reply(timeout=120)

    if not reply or reply.strip() == "0":
        send_message("⏭ No trades selected. Monitor not started.")
        print("No trades selected.")
        return

    # Parse reply
    try:
        selected = [int(x.strip()) for x in reply.split(",")]
    except:
        send_message("❌ Invalid input. No positions added.")
        return

    # Add selected positions
    added = []
    for idx in selected:
        if idx < 1 or idx > len(signals):
            continue
        s = signals[idx - 1]
        token = stock_universe.get(s["symbol"])
        if not token:
            print(f"Token not found for {s['symbol']}")
            continue

        # 🔥 ENTRY CONFIRMATION LOGIC
        api = login()
        current_price = get_ltp(api, s["symbol"], token) if api else None

        if current_price is None:
            print(f"Price fetch failed for {s['symbol']}")
            continue

        if s["trend"] == "bullish":
            if current_price > s["confirmation_high"]:
                add_position(
                    symbol=s["symbol"],
                    token=token,
                    entry=current_price,
                    sl=s["sl"],
                    target=s["target"],
                    trend=s["trend"],
                    qty=s.get("qty", 1)
                )
                added.append(s["symbol"])
            else:
                print(f"⏳ Waiting breakout for {s['symbol']} (bullish)")

        elif s["trend"] == "bearish":
            if current_price < s["confirmation_low"]:
                add_position(
                    symbol=s["symbol"],
                    token=token,
                    entry=current_price,
                    sl=s["sl"],
                    target=s["target"],
                    trend=s["trend"],
                    qty=s.get("qty", 1)
                )
                added.append(s["symbol"])
            else:
                print(f"⏳ Waiting breakdown for {s['symbol']} (bearish)")

    if not added:
        send_message("❌ No valid positions added.")
        return

    # Confirm and start monitor
    send_message(
        f"✅ <b>Positions added:</b> {', '.join(added)}\n"
        f"🔍 Position monitor starting now...\n"
        f"Checking every 5 minutes."
    )
    print(f"Added: {added}")
    print("Starting position monitor...")

    # Start monitor — skip market hours check for testing
    run_monitor(skip_market_hours_check=True)


def listen_for_commands():
    """
    Listen for /exit SYMBOL commands from Telegram.
    Runs in background thread alongside monitor.
    """
    import threading

    def _listen():
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
        last_update_id = None

        # Get current offset
        try:
            resp = requests.get(url, params={"limit": 1, "offset": -1}, timeout=10)
            data = resp.json()
            if data["result"]:
                last_update_id = data["result"][-1]["update_id"]
        except:
            pass

        print("Command listener started. Send /exit SYMBOL to close a position.")

        while True:
            try:
                params = {"timeout": 10, "limit": 5}
                if last_update_id:
                    params["offset"] = last_update_id + 1

                resp = requests.get(url, params=params, timeout=15)
                data = resp.json()

                for update in data.get("result", []):
                    last_update_id = update["update_id"]
                    text = update.get("message", {}).get("text", "").strip()

                    if not text:
                        continue

                    # Handle /exit SYMBOL
                    if text.lower().startswith("/exit"):
                        parts = text.split()
                        if len(parts) < 2:
                            send_message("❌ Usage: /exit SYMBOL\nExample: /exit ASIANPAINT")
                            continue

                        symbol = parts[1].upper()
                        positions = load_positions()
                        found = any(p["symbol"] == symbol for p in positions)

                        if not found:
                            send_message(f"❌ {symbol} not found in open positions.")
                            continue

                        # Calculate P&L before removing
                        for p in positions:
                            if p["symbol"] == symbol:
                                entry = p["entry"]
                                trend = p["trend"]
                                qty = p["qty"]

                                # Get current price
                                api = login()
                                current_price = get_ltp(api, symbol, p["token"]) if api else None

                                if current_price:
                                    if trend == "bullish":
                                        pnl_per_share = round(current_price - entry, 2)
                                    else:
                                        pnl_per_share = round(entry - current_price, 2)

                                    total_pnl = round(pnl_per_share * qty, 0)
                                    pct = round(abs(pnl_per_share) / entry * 100, 2)
                                    sign = "+" if pnl_per_share >= 0 else "-"
                                    emoji = "✅" if pnl_per_share >= 0 else "❌"

                                    msg = (
                                        f"{emoji} <b>MANUAL EXIT — {symbol}</b>\n\n"
                                        f"Entry: ₹{entry} → Exit: ₹{current_price}\n"
                                        f"P&L: {sign}₹{abs(pnl_per_share)}/share | {sign}{pct}%\n"
                                        f"Total P&L: {sign}₹{abs(total_pnl)} ({qty} shares)\n\n"
                                        f"📋 Position removed from monitor."
                                    )
                                else:
                                    msg = f"📋 <b>{symbol}</b> manually exited. Position removed."

                                send_message(msg)
                                break

                        remove_position(symbol)
                        print(f"Manual exit: {symbol} removed from positions.")

                    # Handle /positions — list all open
                    elif text.lower() == "/positions":
                        positions = load_positions()
                        if not positions:
                            send_message("📋 No open positions.")
                            continue

                        lines = ["📋 <b>OPEN POSITIONS</b>\n"]
                        for p in positions:
                            direction = "🟢" if p["trend"] == "bullish" else "🔴"
                            lines.append(
                                f"{direction} <b>{p['symbol']}</b>\n"
                                f"   Entry: ₹{p['entry']} | SL: ₹{p['sl']} | Target: ₹{p['target']}\n"
                                f"   Added: {p['added_at']}"
                            )
                        send_message("\n\n".join(lines))

            except Exception as e:
                print(f"Command listener error: {e}")

            time.sleep(3)

    thread = threading.Thread(target=_listen, daemon=True)
    thread.start()

# ─── Main Monitor Loop ────────────────────────────────────────────────

def run_monitor(skip_market_hours_check=False):
    """Main loop — checks positions every 5 minutes"""
    print("="*50)
    print("POSITION MONITOR STARTED")
    print("Checking every 5 minutes")
    print("="*50)

    # Start command listener in background
    listen_for_commands()

    warned = set()

    while True:
        now = datetime.now()

        # Market hours check
        if not skip_market_hours_check:
            market_open = now.replace(hour=9, minute=15, second=0)
            market_close = now.replace(hour=15, minute=30, second=0)

            if not (market_open <= now <= market_close):
                if now.hour < 9 or (now.hour == 9 and now.minute < 15):
                    print(f"[{now.strftime('%H:%M')}] Market not open yet. Waiting...")
                else:
                    print(f"[{now.strftime('%H:%M')}] Market closed. Monitor stopping.")
                    break
                time.sleep(60)
                continue

        positions = load_positions()

        if not positions:
            print(f"[{now.strftime('%H:%M')}] No open positions.")
            time.sleep(300)
            continue

        print(f"\n[{now.strftime('%H:%M')}] Checking {len(positions)} positions...")

        api = login()
        if not api:
            print("Login failed. Retrying in 5 minutes.")
            time.sleep(300)
            continue

        closed_positions = []
        status_lines = []

        for position in positions:
            symbol = position["symbol"]
            token = position["token"]
            current_price = get_ltp(api, symbol, token)

            if current_price is None:
                print(f"  Could not get price for {symbol}")
                continue

            status = check_position(position, current_price)
            print(f"  {symbol} | ₹{current_price} | {status.upper()}")

            if status == "target_hit":
                send_message(format_target_alert(position, current_price))
                closed_positions.append(symbol)
            elif status == "sl_hit":
                send_message(format_sl_alert(position, current_price))
                closed_positions.append(symbol)
            elif status == "warning" and symbol not in warned:
                send_message(format_warning_alert(position, current_price))
                warned.add(symbol)
            else:
                status_lines.append(format_status_update(position, current_price))

        for symbol in closed_positions:
            remove_position(symbol)
            warned.discard(symbol)

        if status_lines:
            send_message("📊 <b>POSITION UPDATE</b>\n\n" + "\n".join(status_lines))

        time.sleep(300)


# ─── CLI ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "add":
        _, _, symbol, token, entry, sl, target, trend, qty = sys.argv
        add_position(symbol, token, float(entry), float(sl), float(target), trend, int(qty))

    elif len(sys.argv) > 1 and sys.argv[1] == "list":
        positions = load_positions()
        if not positions:
            print("No open positions")
        for p in positions:
            print(f"{p['symbol']} | Entry: {p['entry']} | SL: {p['sl']} | Target: {p['target']} | {p['trend']}")

    elif len(sys.argv) > 1 and sys.argv[1] == "remove":
        symbol = sys.argv[2]
        remove_position(symbol)
        print(f"Removed {symbol}")

    else:
        run_monitor(skip_market_hours_check=True)