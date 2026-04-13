import sys
sys.path.append(".")
from data.angel_api import fetch_all_stocks
from indicators.technical import calculate_indicators, get_latest

WHITELIST = {
    "RELIANCE", "BHARTIARTL", "ITC", "JSWSTEEL", "SHRIRAMFIN",
    "BPCL", "VEDL", "BRITANNIA", "SANOFI", "HCLTECH",
    "HEIDELBERG", "SBIN", "HDFCLIFE", "TECHM", "MUTHOOTFIN"
}

all_data = fetch_all_stocks()

print(f"\n{'Symbol':<15} {'Trend':<10} {'ADX':<8} {'RSI':<8} {'Vol':<8} {'EMA20 dist%':<12} {'Reject reason'}")
print("-"*75)

for symbol in WHITELIST:
    if symbol not in all_data:
        continue
    df = all_data[symbol]
    processed = calculate_indicators(df)
    if processed is None:
        continue
    l = get_latest(processed)

    trend = "bullish" if l["ema20"] > l["ema50"] else "bearish"
    adx = round(l["adx"], 1)
    rsi = round(l["rsi"], 1)
    vol = round(l["vol_ratio"], 2)
    ema20_dist = round(abs(l["close"] - l["ema20"]) / l["close"] * 100, 2)

    if adx < 30:
        reason = f"ADX {adx} < 30"
    elif ema20_dist > 2.0:
        reason = f"EMA20 dist {ema20_dist}% > 2%"
    elif not (35 <= rsi <= 65):
        reason = f"RSI {rsi} out of range"
    elif vol < 1.2:
        reason = f"Vol {vol} < 1.2x"
    else:
        reason = "✅ passes"

    print(f"{symbol:<15} {trend:<10} {adx:<8} {rsi:<8} {vol:<8} {ema20_dist:<12} {reason}")