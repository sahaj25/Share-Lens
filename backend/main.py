import sys
sys.path.append(".")

from data.angel_api import fetch_all_stocks, fetch_candles
from data.token_resolver import resolve_tokens
from indicators.technical import calculate_indicators
from scanners.swing_scanner import scan_stock
from scoring.engine import score_signal
from alerts.telegram_bot import send_swing_alert
from monitor.position_monitor import ask_trades_via_telegram
from datetime import datetime
import pytz


# ─────────────────────────────────────────────
# MARKET TREND (NIFTY)
# ─────────────────────────────────────────────
def get_market_trend():
    try:
        token = "26000"  # NIFTY
        df = fetch_candles(None, "NIFTY", token, days=100)

        if df is None:
            return "neutral"

        df = calculate_indicators(df)
        if df is None:
            return "neutral"

        latest = df.iloc[-1]

        if latest["ema20"] > latest["ema50"]:
            return "bullish"
        else:
            return "bearish"

    except Exception as e:
        print(f"Market trend error: {e}")
        return "neutral"


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
# MAIN SCAN
# ─────────────────────────────────────────────
def run_morning_scan():
    print("="*50)
    print("ShareLens — SWING SCAN")
    ist = pytz.timezone("Asia/Kolkata")
    print(f"Time: {datetime.now(ist).strftime('%d %B %Y | %I:%M %p')}")
    print("="*50)

    # Step 1 — Fetch data
    print("\n[1/4] Fetching data...")
    all_data = fetch_all_stocks()
    if not all_data:
        print("Failed to fetch data. Exiting.")
        return

    total_stocks = len(all_data)

    # 🔥 MARKET TREND
    market_trend = get_market_trend()
    print(f"\nMarket Trend: {market_trend.upper()}")

    # Step 2 — Scan
    print(f"\n[2/4] Scanning {total_stocks} stocks...")
    raw_signals = []

    for symbol, df in all_data.items():
        result = scan_stock(symbol, df)

        if not result:
            continue

        # 🔥 MARKET FILTER
        if market_trend != "neutral" and result["trend"] != market_trend:
            print(f"  ⚠️ Skipped {symbol} — against market")
            continue

        raw_signals.append(result)

    print(f"Passed scanner: {len(raw_signals)} stocks")

    # Step 3 — Score
    print(f"\n[3/4] Scoring signals...")
    print(f"{'SYMBOL':<15} {'SCAN':<10} {'ENGINE':<10} {'TREND':<10} STATUS")

    scored_signals = []

    for signal in raw_signals:
        scanner_score = signal.get("score", "N/A")
        enriched = score_signal(signal)
        engine_score = enriched.get("score", 0)
        trend = enriched.get("trend", "unknown")
        passed = engine_score >= 7.0

        status = "PASS" if passed else "DROP"
        print(f"{enriched['symbol']:<15} {str(scanner_score):<10} {str(engine_score):<10} {trend:<10} {status}")

        if passed:
            # 🔥 EXPOSURE CONTROL
            if check_exposure_limit(scored_signals, enriched):
                scored_signals.append(enriched)
            else:
                print(f"  ⚠️ Skipped {enriched['symbol']} — exposure full")

    print(f"\nFinal signals: {len(scored_signals)}")

    if scored_signals:
        print("\nSignals selected:")
        for s in scored_signals:
            print(f"→ {s['symbol']} | score={s['score']} | trend={s['trend']}")

    # Step 4 — Alert
    print(f"\n[4/4] Sending Telegram alert...")
    send_swing_alert(scored_signals, total_stocks)

    # Step 5 — Monitor
    if scored_signals:
        stock_universe = resolve_tokens()
        ask_trades_via_telegram(scored_signals, stock_universe)

    print("\nScan complete.")
    print("="*50)


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    run_morning_scan()