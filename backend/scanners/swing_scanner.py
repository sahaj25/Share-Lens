import sys
sys.path.append(".")
from data.angel_api import fetch_all_stocks
from indicators.technical import calculate_indicators, get_latest
import numpy as np


def find_support_resistance(df, window=10):
    highs = df["high"].rolling(window=window, center=True).max()
    lows = df["low"].rolling(window=window, center=True).min()
    resistance_levels = df["high"][df["high"] == highs].values
    support_levels = df["low"][df["low"] == lows].values
    resistance_levels = sorted(set(resistance_levels.round(1)), reverse=True)
    support_levels = sorted(set(support_levels.round(1)), reverse=True)
    return support_levels, resistance_levels


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
        target = round(entry + (3 * atr), 1)
    else:
        sl = round(entry + (1.5 * atr), 1)
        target = round(entry - (3 * atr), 1)
    rr = calculate_rr(entry, sl, target)
    return entry, sl, target, rr


def scan_bullish(symbol, latest, processed):
    """Strict bullish conditions — quality only"""
    score = 0
    reasons = []

    # Step 1 — Trend: EMA20 must be above EMA50
    if latest["ema20"] <= latest["ema50"]:
        return None
    score += 20
    reasons.append("EMA20 > EMA50 (bullish trend)")

    # Step 2 — ADX: must be above 25
    if latest["adx"] < 25:
        return None
    score += 20
    reasons.append(f"ADX {latest['adx']:.1f} (strong trend)")

    # Step 3 — RSI: strict — only 35-65 range accepted
    rsi = latest["rsi"]
    if rsi > 65:
        return None  # Getting overbought — skip
    if rsi < 35:
        return None  # Too oversold, risky bounce
    score += 20
    reasons.append(f"RSI {rsi:.1f} (clean entry zone)")

    # Step 4 — Volume: must be above average
    if latest["vol_ratio"] < 1.0:
        return None
    score += 20
    reasons.append(f"Volume {latest['vol_ratio']:.1f}x average")

    # Step 5 — S/R: must not be near resistance
    support_levels, resistance_levels = find_support_resistance(processed)
    proximity_pct = 0.02
    for res in resistance_levels[:5]:
        if abs(latest["close"] - res) / latest["close"] <= proximity_pct and latest["close"] < res:
            return None  # Too close to resistance
    for sup in support_levels[:5]:
        if abs(latest["close"] - sup) / latest["close"] <= proximity_pct:
            score += 20
            reasons.append("at key support")
            break
    else:
        score += 10
        reasons.append("no key level nearby")

    # Step 6 — R/R: minimum 1:2
    entry, sl, target, rr = calculate_sl_target(processed, latest, "bullish")
    if rr < 2.0:
        return None
    score += 0  # R/R already a gate, not scored

    final_score = round((score / 100) * 10, 1)
    if final_score < 7.0:
        return None

    return entry, sl, target, rr, score, final_score, reasons, rsi


def scan_bearish(symbol, latest, processed):
    """Strict bearish conditions — quality only"""
    score = 0
    reasons = []

    # Step 1 — Trend: EMA20 must be below EMA50
    if latest["ema20"] >= latest["ema50"]:
        return None
    score += 20
    reasons.append("EMA20 < EMA50 (bearish trend)")

    # Step 2 — ADX: must be above 30 (stricter for shorts)
    if latest["adx"] < 30:
        return None
    score += 20
    reasons.append(f"ADX {latest['adx']:.1f} (strong downtrend)")

    # Step 3 — RSI: strict — only 45-65 range for shorts
    # We want momentum still bearish but not yet oversold
    rsi = latest["rsi"]
    if rsi > 65:
        return None  # Overbought bounce risk — skip
    if rsi < 40:
        return None  # Already oversold — dangerous to short
    score += 20
    reasons.append(f"RSI {rsi:.1f} (bearish momentum, not oversold)")

    # Step 4 — Volume: must be above average
    if latest["vol_ratio"] < 1.0:
        return None
    score += 20
    reasons.append(f"Volume {latest['vol_ratio']:.1f}x average")

    # Step 5 — S/R: must not be near support
    support_levels, resistance_levels = find_support_resistance(processed)
    proximity_pct = 0.02
    for sup in support_levels[:5]:
        if abs(latest["close"] - sup) / latest["close"] <= proximity_pct and latest["close"] > sup:
            return None  # Too close to support — risky short
    for res in resistance_levels[:5]:
        if abs(latest["close"] - res) / latest["close"] <= proximity_pct:
            score += 20
            reasons.append("at key resistance")
            break
    else:
        score += 10
        reasons.append("no key level nearby")

    # Step 6 — R/R: minimum 1:2
    entry, sl, target, rr = calculate_sl_target(processed, latest, "bearish")
    if rr < 2.0:
        return None

    final_score = round((score / 100) * 10, 1)
    if final_score < 7.0:
        return None

    return entry, sl, target, rr, score, final_score, reasons, rsi


def scan_stock(symbol, df):
    processed = calculate_indicators(df)
    if processed is None or len(processed) < 5:
        return None

    latest = get_latest(processed)

    # Try bullish first
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
    print("Fetching data...")
    all_data = fetch_all_stocks()

    if not all_data:
        print("Failed to fetch data")
        return []

    print(f"\nScanning {len(all_data)} stocks...")
    bullish_signals = []
    bearish_signals = []

    for symbol, df in all_data.items():
        result = scan_stock(symbol, df)
        if result:
            if result["trend"] == "bullish":
                bullish_signals.append(result)
                print(f"  ✅ BULL {symbol} — Score {result['score']}/10 | Entry {result['entry']} | SL {result['sl']} | Target {result['target']}")
            else:
                bearish_signals.append(result)
                print(f"  🔴 BEAR {symbol} — Score {result['score']}/10 | Entry {result['entry']} | SL {result['sl']} | Target {result['target']}")
        else:
            print(f"  ✗ {symbol} — rejected")

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