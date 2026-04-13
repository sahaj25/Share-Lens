import sys
sys.path.append(".")
from indicators.technical import calculate_indicators, get_latest
import numpy as np

# Stocks with proven backtest accuracy
WHITELIST = {
    "RELIANCE", "BHARTIARTL", "ITC", "JSWSTEEL", "SHRIRAMFIN",
    "BPCL", "VEDL", "BRITANNIA", "SANOFI", "HCLTECH",
    "HEIDELBERG", "SBIN", "HDFCLIFE", "TECHM", "MUTHOOTFIN"
}


def calculate_rr(entry, sl, target):
    risk = abs(entry - sl)
    reward = abs(target - entry)
    if risk == 0:
        return 0
    return reward / risk


def calculate_sl_target(df, latest, trend):
    current_price = latest["close"]
    atr = (df["high"] - df["low"]).rolling(14).mean().iloc[-1]
    entry = current_price
    if trend == "bullish":
        sl = round(entry - (1.5 * atr), 1)
        target = round(entry + (2.5 * atr), 1)
    else:
        sl = round(entry + (1.5 * atr), 1)
        target = round(entry - (2.5 * atr), 1)
    rr = calculate_rr(entry, sl, target)
    return entry, sl, target, rr


def scan_bullish(symbol, latest, processed):
    """Strict bullish — pullback to EMA20 in uptrend"""
    price = latest["close"]
    ema20 = latest["ema20"]
    ema50 = latest["ema50"]
    adx = latest["adx"]
    rsi = latest["rsi"]
    vol = latest["vol_ratio"]

    # Step 1 — Trend
    if ema20 <= ema50:
        return None

    # Step 2 — ADX strength
    if adx < 30:
        return None

    # Step 3 — Pullback to EMA20 (within 2%)
    price_to_ema20_pct = abs(price - ema20) / price * 100
    if price_to_ema20_pct > 2.5:
        return None

    # Step 4 — RSI in valid range
    if not (35 <= rsi <= 65):
        return None

    # Step 5 — Volume confirmation
    if vol < 1.2:
        return None

    # Step 6 — R/R
    entry, sl, target, rr = calculate_sl_target(processed, latest, "bullish")
    if rr < 1.5:
        return None

    # Score
    score = 0
    score += 20  # trend confirmed
    score += 20 if adx >= 35 else 15
    score += 20 if 40 <= rsi <= 60 else 15
    score += 20 if vol >= 1.5 else 15
    score += 20 if price_to_ema20_pct <= 1.0 else 15  # tighter pullback = better
    final_score = round((score / 100) * 10, 1)

    reasons = [
        f"EMA20 > EMA50 (bullish trend)",
        f"Price pulled back to EMA20 ({price_to_ema20_pct:.1f}% away)",
        f"ADX {adx:.1f} (strong trend)",
        f"RSI {rsi:.1f} (valid entry zone)",
        f"Volume {vol:.1f}x average",
    ]

    return entry, sl, target, rr, score, final_score, reasons, rsi


def scan_bearish(symbol, latest, processed):
    """Strict bearish — pullback to EMA20 in downtrend"""
    price = latest["close"]
    ema20 = latest["ema20"]
    ema50 = latest["ema50"]
    adx = latest["adx"]
    rsi = latest["rsi"]
    vol = latest["vol_ratio"]

    # Step 1 — Trend
    if ema20 >= ema50:
        return None

    # Step 2 — ADX strength
    if adx < 30:
        return None

    # Step 3 — Pullback to EMA20 (within 2%)
    price_to_ema20_pct = abs(price - ema20) / price * 100
    if price_to_ema20_pct > 2.5:
        return None

    # Step 4 — RSI in valid range
    if not (35 <= rsi <= 65):
        return None

    # Step 5 — Volume confirmation
    if vol < 1.2:
        return None

    # Step 6 — R/R
    entry, sl, target, rr = calculate_sl_target(processed, latest, "bearish")
    if rr < 1.5:
        return None

    # Score
    score = 0
    score += 20  # trend confirmed
    score += 20 if adx >= 35 else 15
    score += 20 if 40 <= rsi <= 60 else 15
    score += 20 if vol >= 1.5 else 15
    score += 20 if price_to_ema20_pct <= 1.0 else 15
    final_score = round((score / 100) * 10, 1)

    reasons = [
        f"EMA20 < EMA50 (bearish trend)",
        f"Price pulled back to EMA20 ({price_to_ema20_pct:.1f}% away)",
        f"ADX {adx:.1f} (strong downtrend)",
        f"RSI {rsi:.1f} (valid short zone)",
        f"Volume {vol:.1f}x average",
    ]

    return entry, sl, target, rr, score, final_score, reasons, rsi


def scan_stock(symbol, df):
    """Scan a single stock — whitelist check + bullish/bearish"""

    # Only trade whitelisted stocks
    if symbol not in WHITELIST:
        return None

    processed = calculate_indicators(df)
    if processed is None or len(processed) < 5:
        return None

    latest = get_latest(processed)

    # Try bullish
    bull = scan_bullish(symbol, latest, processed)
    if bull:
        entry, sl, target, rr, score, final_score, reasons, rsi = bull
        sl_pct = round(abs(entry - sl) / entry * 100, 1)
        target_pct = round(abs(target - entry) / entry * 100, 1)
        return {
            "symbol": symbol,
            "trend": "bullish",
            "score": final_score,
            "entry": round(entry, 1),
            "sl": round(sl, 1),
            "target": round(target, 1),
            "sl_pct": sl_pct,
            "target_pct": target_pct,
            "rr": round(rr, 2),
            "rsi": round(rsi, 1),
            "adx": round(latest["adx"], 1),
            "vol_ratio": round(latest["vol_ratio"], 2),
            "reasons": reasons,
            "close": latest["close"],
        }

    # Try bearish
    bear = scan_bearish(symbol, latest, processed)
    if bear:
        entry, sl, target, rr, score, final_score, reasons, rsi = bear
        sl_pct = round(abs(entry - sl) / entry * 100, 1)
        target_pct = round(abs(target - entry) / entry * 100, 1)
        return {
            "symbol": symbol,
            "trend": "bearish",
            "score": final_score,
            "entry": round(entry, 1),
            "sl": round(sl, 1),
            "target": round(target, 1),
            "sl_pct": sl_pct,
            "target_pct": target_pct,
            "rr": round(rr, 2),
            "rsi": round(rsi, 1),
            "adx": round(latest["adx"], 1),
            "vol_ratio": round(latest["vol_ratio"], 2),
            "reasons": reasons,
            "close": latest["close"],
        }

    return None


def run_swing_scan():
    from data.angel_api import fetch_all_stocks

    print("Fetching data...")
    all_data = fetch_all_stocks()
    if not all_data:
        print("Failed to fetch data")
        return []

    print(f"\nScanning {len(WHITELIST)} whitelisted stocks...")
    bullish_signals = []
    bearish_signals = []

    for symbol, df in all_data.items():
        if symbol not in WHITELIST:
            continue
        result = scan_stock(symbol, df)
        if result:
            if result["trend"] == "bullish":
                bullish_signals.append(result)
                print(f"  ✅ BULL {symbol} — Score {result['score']}/10 | Entry {result['entry']} | SL {result['sl']} | Target {result['target']}")
            else:
                bearish_signals.append(result)
                print(f"  🔴 BEAR {symbol} — Score {result['score']}/10 | Entry {result['entry']} | SL {result['sl']} | Target {result['target']}")
        else:
            print(f"  ✗ {symbol} — no setup")

    total = bullish_signals + bearish_signals
    print(f"\n{'='*50}")
    print(f"BULLISH: {len(bullish_signals)} | BEARISH: {len(bearish_signals)} | TOTAL: {len(total)}")
    return total


if __name__ == "__main__":
    signals = run_swing_scan()
    if not signals:
        print("\nNo clean setups today. WAIT.")
    else:
        print("\nFINAL SIGNALS:")
        for s in signals:
            direction = "🟢 BULL" if s["trend"] == "bullish" else "🔴 BEAR"
            print(f"\n{direction} {s['symbol']} — {s['score']}/10")
            print(f"  Entry: ₹{s['entry']} | SL: ₹{s['sl']} ({s['sl_pct']}%) | Target: ₹{s['target']} ({s['target_pct']}%)")
            print(f"  R/R: 1:{s['rr']} | RSI: {s['rsi']} | ADX: {s['adx']} | Vol: {s['vol_ratio']}x")
            print(f"  Reasons: {' + '.join(s['reasons'])}")