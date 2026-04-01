import sys
sys.path.append(".")

from data.angel_api import fetch_all_stocks
from indicators.technical import calculate_indicators, get_latest
from scanners.swing_scanner import scan_stock
from scoring.engine import score_signal
from alerts.telegram_bot import send_swing_alert
from datetime import datetime


def run_morning_scan():
    print("="*50)
    print(f"STOKIFY — SWING SCAN")
    print(f"Time: {datetime.now().strftime('%d %B %Y | %I:%M %p')}")
    print("="*50)

    # Step 1 — Fetch data
    print("\n[1/4] Fetching Nifty 50 data...")
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
    scored_signals = []
    for signal in raw_signals:
        enriched = score_signal(signal)
        if enriched["score"] >= 7.0:
            scored_signals.append(enriched)
            print(f"  ✅ {enriched['symbol']} — {enriched['score']}/10")

    print(f"Final signals: {len(scored_signals)}")

    # Step 4 — Send Telegram alert
    print(f"\n[4/4] Sending Telegram alert...")
    send_swing_alert(scored_signals, total_stocks)

    print("\nScan complete.")
    print("="*50)


if __name__ == "__main__":
    run_morning_scan()