def calculate_hold_days(adx, rsi, vol_ratio):
    """Estimate how many days to hold based on trend strength"""
    if adx >= 35:
        base_days = "3-5 days"
    elif adx >= 25:
        base_days = "5-8 days"
    else:
        base_days = "7-10 days"
    return base_days


def calculate_position_size(entry, sl, total_capital=25000, risk_per_trade=500):
    """
    Calculate how many shares to buy
    Risk per trade = max money you're willing to lose on this trade
    """
    risk_per_share = abs(entry - sl)
    if risk_per_share == 0:
        return 0
    
    qty = int(risk_per_trade / risk_per_share)
    capital_needed = qty * entry
    
    # Cap at 40% of total capital per trade
    max_capital = total_capital * 0.4
    if capital_needed > max_capital:
        qty = int(max_capital / entry)
    
    return qty


def score_signal(signal):
    """
    Detailed scoring breakdown for a signal
    Returns enriched signal with full scoring details
    """
    breakdown = {}
    total = 0

    # Trend direction — 20 pts
    if signal["trend"] == "bullish":
        breakdown["trend"] = 20
        total += 20

    # ADX strength — 20 pts
    adx = signal["adx"]
    if adx >= 35:
        breakdown["adx"] = 20
        total += 20
    elif adx >= 25:
        breakdown["adx"] = 15
        total += 15
    else:
        breakdown["adx"] = 0

    # RSI timing — 20 pts
    rsi = signal["rsi"]
    if 45 <= rsi <= 60:
        breakdown["rsi"] = 20
        total += 20
    elif rsi < 45:
        breakdown["rsi"] = 18  # Oversold — slightly less ideal but still good
        total += 18
    elif rsi <= 70:
        breakdown["rsi"] = 10
        total += 10
    else:
        breakdown["rsi"] = 0

    # Volume — 20 pts
    vol = signal["vol_ratio"]
    if vol >= 2.0:
        breakdown["volume"] = 20
        total += 20
    elif vol >= 1.5:
        breakdown["volume"] = 15
        total += 15
    elif vol >= 1.0:
        breakdown["volume"] = 10
        total += 10
    else:
        breakdown["volume"] = 0

    # R/R quality — 20 pts
    rr = signal["rr"]
    if rr >= 2.5:
        breakdown["rr"] = 20
        total += 20
    elif rr >= 2.0:
        breakdown["rr"] = 15
        total += 15
    elif rr >= 1.5:
        breakdown["rr"] = 10
        total += 10
    else:
        breakdown["rr"] = 0

    # Final score out of 10
    final_score = round((total / 100) * 10, 1)

    # Add enriched data to signal
    signal["score"] = final_score
    signal["score_breakdown"] = breakdown
    signal["raw_score"] = total
    signal["hold_days"] = calculate_hold_days(adx, rsi, vol)
    signal["qty"] = calculate_position_size(signal["entry"], signal["sl"])
    signal["capital_needed"] = round(signal["qty"] * signal["entry"], 0)
    signal["max_loss"] = round(signal["qty"] * abs(signal["entry"] - signal["sl"]), 0)
    signal["max_profit"] = round(signal["qty"] * abs(signal["target"] - signal["entry"]), 0)

    return signal


# Quick test
if __name__ == "__main__":
    # Simulate the ONGC signal we got
    test_signal = {
        "symbol": "ONGC",
        "score": 8.0,
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
        "reasons": ["EMA20 > EMA50", "ADX 32.2", "Volume 1.5x", "no key level nearby"],
        "close": 284.6,
    }

    enriched = score_signal(test_signal)

    print(f"Symbol: {enriched['symbol']}")
    print(f"Final Score: {enriched['score']}/10")
    print(f"Raw Score: {enriched['raw_score']}/100")
    print(f"Breakdown: {enriched['score_breakdown']}")
    print(f"Hold: {enriched['hold_days']}")
    print(f"Qty to buy: {enriched['qty']} shares")
    print(f"Capital needed: ₹{enriched['capital_needed']}")
    print(f"Max loss: ₹{enriched['max_loss']}")
    print(f"Max profit: ₹{enriched['max_profit']}")