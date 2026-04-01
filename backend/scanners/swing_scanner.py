import sys
sys.path.append(".")
from data.angel_api import fetch_all_stocks
from indicators.technical import calculate_indicators, get_latest
import pandas as pd
import numpy as np


def find_support_resistance(df, window=10):
    """Find key S/R levels from recent price history"""
    highs = df["high"].rolling(window=window, center=True).max()
    lows = df["low"].rolling(window=window, center=True).min()

    resistance_levels = df["high"][df["high"] == highs].values
    support_levels = df["low"][df["low"] == lows].values

    resistance_levels = sorted(set(resistance_levels.round(1)), reverse=True)
    support_levels = sorted(set(support_levels.round(1)), reverse=True)

    return support_levels, resistance_levels


def check_sr_quality(current_price, support_levels, resistance_levels):
    """
    Check where price is relative to S/R levels
    Returns: (score, label)
    """
    proximity_pct = 0.02  # within 2%

    # Check if near support
    for sup in support_levels[:5]:
        if abs(current_price - sup) / current_price <= proximity_pct:
            return 20, "at key support"

    # Check if breakout above resistance
    for res in resistance_levels[:5]:
        if current_price > res and abs(current_price - res) / current_price <= proximity_pct:
            return 20, "breaking out above resistance"

    # Check if approaching resistance — avoid
    for res in resistance_levels[:5]:
        if abs(current_price - res) / current_price <= proximity_pct and current_price < res:
            return 0, "near resistance — avoid"

    # Price is in middle — neutral
    return 10, "no key level nearby"


def calculate_rr(entry, sl, target):
    """Calculate Risk/Reward ratio"""
    risk = abs(entry - sl)
    reward = abs(target - entry)
    if risk == 0:
        return 0
    return reward / risk


def calculate_sl_target(df, latest, trend):
    """Auto calculate entry, SL and target"""
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


def scan_stock(symbol, df):
    """
    Run all 6 steps on a single stock.
    Returns signal dict if passes, None if rejected.
    """
    processed = calculate_indicators(df)
    if processed is None or len(processed) < 5:
        return None

    latest = get_latest(processed)
    score = 0
    reasons = []

    # --- Step 1: Trend Check ---
    if latest["ema20"] > latest["ema50"]:
        trend = "bullish"
        score += 20
        reasons.append("EMA20 > EMA50 (bullish trend)")
    elif latest["ema20"] < latest["ema50"]:
        trend = "bearish"
        # For now we only take bullish setups
        return None
    else:
        return None  # No clear trend

    # --- Step 2: ADX Strength ---
    if latest["adx"] >= 25:
        score += 20
        reasons.append(f"ADX {latest['adx']:.1f} (strong trend)")
    else:
        return None  # Weak trend, reject

    # --- Step 3: RSI Entry Timing ---
    rsi = latest["rsi"]
    if 40 <= rsi <= 60:
        score += 20
        reasons.append(f"RSI {rsi:.1f} (good entry zone)")
    elif rsi < 40:
        score += 20
        reasons.append(f"RSI {rsi:.1f} (oversold bounce opportunity)")
    elif rsi > 70:
        return None  # Overbought, reject
    else:
        score += 10  # RSI 60-70, partial score

    # --- Step 4: Volume Confirmation ---
    if latest["vol_ratio"] >= 1.0:
        score += 20
        reasons.append(f"Volume {latest['vol_ratio']:.1f}x average")
    else:
        return None  # Below average volume, reject

    # --- Step 5: S/R Check ---
    support_levels, resistance_levels = find_support_resistance(processed)
    sr_score, sr_label = check_sr_quality(latest["close"], support_levels, resistance_levels)

    if sr_score == 0:
        return None  # Near resistance, reject

    score += sr_score
    reasons.append(sr_label)

    # --- Step 6: R/R Calculation ---
    entry, sl, target, rr = calculate_sl_target(processed, latest, trend)

    if rr < 1.5:
        return None  # Below 1:1.5 R/R, reject

    # --- Final Score ---
    final_score = round((score / 100) * 10, 1)

    if final_score < 7.0:
        return None  # Below threshold

    sl_pct = round(abs(entry - sl) / entry * 100, 1)
    target_pct = round(abs(target - entry) / entry * 100, 1)

    return {
        "symbol": symbol,
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
        "trend": trend,
        "reasons": reasons,
        "close": latest["close"],
    }


def run_swing_scan():
    """Main function — scan all stocks and return valid setups"""
    print("Fetching data...")
    all_data = fetch_all_stocks()

    if not all_data:
        print("Failed to fetch data")
        return []

    print(f"\nScanning {len(all_data)} stocks...")
    signals = []

    for symbol, df in all_data.items():
        result = scan_stock(symbol, df)
        if result:
            signals.append(result)
            print(f"  ✅ {symbol} — Score {result['score']}/10 | Entry {result['entry']} | SL {result['sl']} | Target {result['target']} | R/R 1:{result['rr']}")
        else:
            print(f"  ✗ {symbol} — rejected")

    print(f"\n{'='*50}")
    print(f"SETUPS FOUND: {len(signals)}")
    print(f"REJECTED: {len(all_data) - len(signals)}")

    return signals


if __name__ == "__main__":
    signals = run_swing_scan()

    if signals:
        print("\nFINAL SIGNALS:")
        for s in signals:
            print(f"\n{s['symbol']} — {s['score']}/10")
            print(f"  Entry: ₹{s['entry']} | SL: ₹{s['sl']} ({s['sl_pct']}%) | Target: ₹{s['target']} ({s['target_pct']}%)")
            print(f"  R/R: 1:{s['rr']} | RSI: {s['rsi']} | ADX: {s['adx']} | Vol: {s['vol_ratio']}x")
            print(f"  Reasons: {' + '.join(s['reasons'])}")
    else:
        print("\nNo clean setups today. WAIT.")