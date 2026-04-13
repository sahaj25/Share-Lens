import sys
sys.path.append(".")

from data.angel_api import fetch_all_stocks
from data.token_resolver import resolve_tokens
from indicators.technical import calculate_indicators, get_latest
from scanners.swing_scanner import scan_stock
from scoring.engine import score_signal
from alerts.telegram_bot import send_swing_alert
from monitor.position_monitor import ask_trades_via_telegram
from datetime import datetime
import pytz

def run_morning_scan():
    print("="*50)
    print(f"ShareLens — SWING SCAN")
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

    # Step 2 — Scan each stock
    print(f"\n[2/4] Scanning {total_stocks} stocks...")
    raw_signals = []
    for symbol, df in all_data.items():
        result = scan_stock(symbol, df)
        if result:
            raw_signals.append(result)

    print(f"Passed scanner: {len(raw_signals)} stocks")

    # Step 3 — Score each signal
    print(f"\n[3/4] Scoring signals...")
    print(f"  {'SYMBOL':<15} {'SCANNER SCORE':<15} {'ENGINE SCORE':<15} {'TREND':<12} {'PASS?'}")
    print(f"  {'-'*65}")

    scored_signals = []
    for signal in raw_signals:
        scanner_score = signal.get("score", "N/A")
        enriched = score_signal(signal)
        engine_score = enriched.get("score", 0)
        trend = enriched.get("trend", "unknown")
        passed = engine_score >= 7.0

        status = "✅ PASS" if passed else f"❌ DROPPED (score={engine_score})"
        print(f"  {enriched['symbol']:<15} {str(scanner_score):<15} {str(engine_score):<15} {trend:<12} {status}")

        if passed:
            scored_signals.append(enriched)

    print(f"\nFinal signals: {len(scored_signals)}")

    if scored_signals:
        print(f"\n  Signals being sent to Telegram:")
        for s in scored_signals:
            print(f"    → {s['symbol']} | score={s['score']} | trend={s['trend']}")

    # Step 4 — Send Telegram alert
    print(f"\n[4/4] Sending Telegram alert...")
    send_swing_alert(scored_signals, total_stocks)

    # Step 5 — Ask which trades via Telegram + auto start monitor
    if scored_signals:
        stock_universe = resolve_tokens()
        ask_trades_via_telegram(scored_signals, stock_universe)

    print("\nScan complete.")
    print("="*50)


if __name__ == "__main__":
    run_morning_scan()