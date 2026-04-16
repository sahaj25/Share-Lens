import sys
sys.path.append(".")

from data.angel_api import fetch_all_stocks
from indicators.technical import calculate_indicators
from data.token_resolver import resolve_tokens
from alerts.telegram_bot import send_swing_alert
from monitor.position_monitor import ask_trades_via_telegram

from datetime import datetime
import pytz
import pandas as pd


# ─────────────────────────────────────────────
# MARKET TREND
# ─────────────────────────────────────────────
def get_market_trend(all_data):
    try:
        df = all_data.get("NIFTY", None)
        if df is None:
            return "neutral"

        df = calculate_indicators(df)
        latest = df.iloc[-1]

        return "bullish" if latest["ema20"] > latest["ema50"] else "bearish"
    except:
        return "neutral"


# ─────────────────────────────────────────────
# TRAILING SL LOGIC
# ─────────────────────────────────────────────
def apply_trailing_sl(signal, current_price):
    entry = signal["entry"]
    target = signal["target"]
    sl = signal["sl"]

    current_sl = sl

    if signal["trend"] == "bullish":
        move = target - entry

        # move to breakeven
        if current_price >= entry + move * 0.3:
            current_sl = max(current_sl, entry)

        # lock profit
        if current_price >= entry + move * 0.7:
            current_sl = max(current_sl, entry + move * 0.5)

    else:
        move = entry - target

        if current_price <= entry - move * 0.3:
            current_sl = min(current_sl, entry)

        if current_price <= entry - move * 0.7:
            current_sl = min(current_sl, entry - move * 0.5)

    return round(current_sl, 2)


# ─────────────────────────────────────────────
# STRATEGY (RELAXED + BACKTEST ALIGNED)
# ─────────────────────────────────────────────
def generate_signal(symbol, df):
    df = calculate_indicators(df)
    if df is None or len(df) < 50:
        return None

    latest = df.iloc[-1]

    price = latest["close"]
    ema20 = latest["ema20"]
    ema50 = latest["ema50"]
    adx = latest["adx"]
    rsi = latest["rsi"]
    vol = latest["vol_ratio"]

    atr = (df["high"] - df["low"]).rolling(14).mean().iloc[-1]

    if pd.isna(atr) or atr == 0:
        return None

    # ── Bullish ──
    if ema20 > ema50 and adx >= 25:
        if abs(price - ema20) / price * 100 <= 3.0 and vol >= 1.0 and 30 <= rsi <= 70:

            sl = round(price - (1.2 * atr), 2)
            target = round(price + (3 * atr), 2)

            rr = abs(target - price) / abs(price - sl)
            if rr < 1.3:
                return None

            return {
                "symbol": symbol,
                "trend": "bullish",
                "entry": round(price, 2),
                "sl": sl,
                "target": target,
                "score": 8
            }

    # ── Bearish ──
    if ema20 < ema50 and adx >= 25:
        if abs(price - ema20) / price * 100 <= 3.0 and vol >= 1.0 and 30 <= rsi <= 70:

            sl = round(price + (1.2 * atr), 2)
            target = round(price - (3 * atr), 2)

            rr = abs(target - price) / abs(price - sl)
            if rr < 1.3:
                return None

            return {
                "symbol": symbol,
                "trend": "bearish",
                "entry": round(price, 2),
                "sl": sl,
                "target": target,
                "score": 8
            }

    return None


# ─────────────────────────────────────────────
# EXPOSURE CONTROL
# ─────────────────────────────────────────────
def check_exposure_limit(signals, new_signal, max_per_side=2, max_total=4):
    bull = sum(1 for s in signals if s["trend"] == "bullish")
    bear = sum(1 for s in signals if s["trend"] == "bearish")

    if len(signals) >= max_total:
        return False

    if new_signal["trend"] == "bullish" and bull >= max_per_side:
        return False

    if new_signal["trend"] == "bearish" and bear >= max_per_side:
        return False

    return True


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def run_morning_scan():
    print("="*50)
    print("ShareLens — SWING SCAN")
    ist = pytz.timezone("Asia/Kolkata")
    print(f"Time: {datetime.now(ist).strftime('%d %B %Y | %I:%M %p')}")
    print("="*50)

    print("\n[1/3] Fetching data...")
    all_data = fetch_all_stocks()

    if not all_data:
        print("Failed to fetch data.")
        return

    market_trend = get_market_trend(all_data)
    print(f"\nMarket Trend: {market_trend.upper()}")

    print("\n[2/3] Generating signals...")

    signals = []

    for symbol, df in all_data.items():
        signal = generate_signal(symbol, df)

        if not signal:
            continue

        # Market filter
        if market_trend != "neutral" and signal["trend"] != market_trend:
            continue

        if check_exposure_limit(signals, signal):
            signals.append(signal)

    print(f"\nFinal signals: {len(signals)}")

    for s in signals:
        print(f"→ {s['symbol']} | {s['trend']} | Entry={s['entry']} | SL={s['sl']} | TGT={s['target']}")

    print("\n[3/3] Sending alerts...")
    send_swing_alert(signals, len(all_data))

    # 🔥 MONITOR WITH TRAILING SL
    if signals:
        stock_universe = resolve_tokens()

        # Attach trailing SL initially
        for s in signals:
            s["trailing_sl"] = s["sl"]

        ask_trades_via_telegram(signals, stock_universe)

    print("\nScan complete.")


# ─────────────────────────────────────────────
if __name__ == "__main__":
    run_morning_scan()