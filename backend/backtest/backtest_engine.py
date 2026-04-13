import sys
sys.path.append(".")

import json
import time
import os
import pyotp
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from SmartApi import SmartConnect
from dotenv import load_dotenv
from indicators.technical import calculate_indicators
from data.token_resolver import resolve_tokens

load_dotenv()

BACKTEST_RESULTS_FILE = "storage/backtest_results.json"
WARMUP_DAYS = 50
FORWARD_DAYS = 15

WHITELIST = {
    "RELIANCE", "BHARTIARTL", "ITC", "JSWSTEEL", "SHRIRAMFIN",
    "BPCL", "VEDL", "BRITANNIA", "SANOFI", "HCLTECH",
    "HEIDELBERG", "SBIN", "HDFCLIFE", "TECHM", "MUTHOOTFIN"
}


# ─── Login ───────────────────────────────────────────────────────────

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


# ─── Data Fetching ───────────────────────────────────────────────────

def fetch_full_history(api, symbol, token, days=400):
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        params = {
            "exchange": "NSE",
            "symboltoken": token,
            "interval": "ONE_DAY",
            "fromdate": start_date.strftime("%Y-%m-%d %H:%M"),
            "todate": end_date.strftime("%Y-%m-%d %H:%M"),
        }
        response = api.getCandleData(params)
        if response["status"] == False:
            return None
        candles = response["data"]
        if not candles or len(candles) < WARMUP_DAYS + 20:
            return None
        df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp")
        df = df.astype({"open": float, "high": float, "low": float, "close": float, "volume": float})
        df["symbol"] = symbol
        return df
    except:
        return None


# ─── Trade Simulation ────────────────────────────────────────────────

def simulate_trade(df, signal_day_idx, signal):
    entry = signal["entry"]
    sl = signal["sl"]
    target = signal["target"]
    trend = signal["trend"]

    future = df.iloc[signal_day_idx + 1: signal_day_idx + 1 + FORWARD_DAYS]

    if len(future) == 0:
        return "timeout", entry, entry

    for _, candle in future.iterrows():
        high = candle["high"]
        low = candle["low"]
        if trend == "bullish":
            if high >= target:
                return "win", entry, target
            if low <= sl:
                return "loss", entry, sl
        else:
            if low <= target:
                return "win", entry, target
            if high >= sl:
                return "loss", entry, sl

    exit_price = future.iloc[-1]["close"]

    # Profitable timeout = win, unprofitable = loss
    if trend == "bullish":
        return ("win", entry, exit_price) if exit_price > entry else ("loss", entry, exit_price)
    else:
        return ("win", entry, exit_price) if exit_price < entry else ("loss", entry, exit_price)


# ─── Core Backtest ───────────────────────────────────────────────────

def backtest_stock(symbol, df):
    trades = []
    total_days = len(df)

    for i in range(WARMUP_DAYS, total_days - FORWARD_DAYS):
        window = df.iloc[:i + 1].copy()
        processed = calculate_indicators(window)
        if processed is None or len(processed) < 5:
            continue

        latest = processed.iloc[-1]
        signal = None

        price = latest["close"]
        ema20 = latest["ema20"]
        ema50 = latest["ema50"]
        adx = latest["adx"]
        rsi = latest["rsi"]
        vol = latest["vol_ratio"]
        atr = (window["high"] - window["low"]).rolling(14).mean().iloc[-1]

        if pd.isna(atr) or atr == 0:
            continue

        # ── Bullish ──
        if ema20 > ema50 and adx >= 30:
            price_to_ema20_pct = abs(price - ema20) / price * 100
            if price_to_ema20_pct <= 2.0 and vol >= 1.2 and 35 <= rsi <= 65:
                entry = price
                sl = round(entry - (1.5 * atr), 2)
                target = round(entry + (2.5 * atr), 2)
                rr = round(abs(target - entry) / abs(entry - sl), 2) if abs(entry - sl) > 0 else 0
                if rr >= 1.5:
                    score = 0
                    score += 20
                    score += 20 if adx >= 35 else 15
                    score += 20 if 40 <= rsi <= 60 else 15
                    score += 20 if vol >= 1.5 else 15
                    score += 20 if price_to_ema20_pct <= 1.0 else 15
                    signal = {
                        "symbol": symbol,
                        "trend": "bullish",
                        "entry": round(entry, 2),
                        "sl": sl,
                        "target": target,
                        "rr": rr,
                        "score": round((score / 100) * 10, 1),
                        "date": str(df.index[i].date()),
                    }

        # ── Bearish ──
        if not signal and ema20 < ema50 and adx >= 30:
            price_to_ema20_pct = abs(price - ema20) / price * 100
            if price_to_ema20_pct <= 2.0 and vol >= 1.2 and 35 <= rsi <= 65:
                entry = price
                sl = round(entry + (1.5 * atr), 2)
                target = round(entry - (2.5 * atr), 2)
                rr = round(abs(target - entry) / abs(entry - sl), 2) if abs(entry - sl) > 0 else 0
                if rr >= 1.5:
                    score = 0
                    score += 20
                    score += 20 if adx >= 35 else 15
                    score += 20 if 40 <= rsi <= 60 else 15
                    score += 20 if vol >= 1.5 else 15
                    score += 20 if price_to_ema20_pct <= 1.0 else 15
                    signal = {
                        "symbol": symbol,
                        "trend": "bearish",
                        "entry": round(entry, 2),
                        "sl": sl,
                        "target": target,
                        "rr": rr,
                        "score": round((score / 100) * 10, 1),
                        "date": str(df.index[i].date()),
                    }

        if not signal:
            continue

        outcome, entry_price, exit_price = simulate_trade(df, i, signal)

        pnl_pct = round((exit_price - entry_price) / entry_price * 100, 2) if signal["trend"] == "bullish" \
            else round((entry_price - exit_price) / entry_price * 100, 2)

        trades.append({
            "symbol": symbol,
            "date": signal["date"],
            "trend": signal["trend"],
            "entry": entry_price,
            "sl": signal["sl"],
            "target": signal["target"],
            "exit_price": round(exit_price, 2),
            "rr": signal["rr"],
            "score": signal["score"],
            "outcome": outcome,
            "pnl_pct": pnl_pct,
        })

    return trades


# ─── Accuracy Tracker ────────────────────────────────────────────────

def calculate_accuracy(all_trades):
    if not all_trades:
        return {}

    wins = [t for t in all_trades if t["outcome"] == "win"]
    losses = [t for t in all_trades if t["outcome"] == "loss"]
    timeouts = [t for t in all_trades if t["outcome"] == "timeout"]

    total = len(all_trades)
    win_rate = round(len(wins) / total * 100, 1) if total > 0 else 0
    avg_win_pct = round(sum(t["pnl_pct"] for t in wins) / len(wins), 2) if wins else 0
    avg_loss_pct = round(sum(t["pnl_pct"] for t in losses) / len(losses), 2) if losses else 0
    loss_rate = len(losses) / total if total > 0 else 0
    expectancy = round((win_rate / 100 * avg_win_pct) + (loss_rate * avg_loss_pct), 2)

    bull_trades = [t for t in all_trades if t["trend"] == "bullish"]
    bear_trades = [t for t in all_trades if t["trend"] == "bearish"]

    return {
        "total_trades": total,
        "wins": len(wins),
        "losses": len(losses),
        "timeouts": len(timeouts),
        "win_rate": win_rate,
        "avg_win_pct": avg_win_pct,
        "avg_loss_pct": avg_loss_pct,
        "expectancy": expectancy,
        "bullish_trades": len(bull_trades),
        "bullish_win_rate": round(len([t for t in bull_trades if t["outcome"] == "win"]) / len(bull_trades) * 100, 1) if bull_trades else 0,
        "bearish_trades": len(bear_trades),
        "bearish_win_rate": round(len([t for t in bear_trades if t["outcome"] == "win"]) / len(bear_trades) * 100, 1) if bear_trades else 0,
    }


def print_accuracy_report(stats, all_trades):
    print("\n" + "="*55)
    print("BACKTEST RESULTS — ACCURACY REPORT")
    print("="*55)
    print(f"Total Signals Generated : {stats['total_trades']}")
    print(f"Wins                    : {stats['wins']}")
    print(f"Losses                  : {stats['losses']}")
    print(f"Timeouts                : {stats['timeouts']}")
    print(f"Win Rate                : {stats['win_rate']}%")
    print(f"Avg Win                 : +{stats['avg_win_pct']}%")
    print(f"Avg Loss                : {stats['avg_loss_pct']}%")
    print(f"Expectancy              : {stats['expectancy']}%")
    print("-"*55)
    print(f"Bullish  : {stats['bullish_trades']} trades | WR: {stats['bullish_win_rate']}%")
    print(f"Bearish  : {stats['bearish_trades']} trades | WR: {stats['bearish_win_rate']}%")
    print("="*55)

    stock_stats = {}
    for t in all_trades:
        s = t["symbol"]
        if s not in stock_stats:
            stock_stats[s] = {"wins": 0, "total": 0}
        stock_stats[s]["total"] += 1
        if t["outcome"] == "win":
            stock_stats[s]["wins"] += 1

    ranked = sorted(
        [(s, v["wins"], v["total"], round(v["wins"] / v["total"] * 100, 1))
         for s, v in stock_stats.items() if v["total"] >= 2],
        key=lambda x: x[3], reverse=True
    )
    if ranked:
        print("\nTOP PERFORMING STOCKS:")
        for sym, wins, total, wr in ranked[:15]:
            print(f"  {sym:<15} {wins}/{total} trades | {wr}% WR")


# ─── Main Runner ─────────────────────────────────────────────────────

def run_backtest():
    print("="*55)
    print("STOKIFY — BACKTEST ENGINE")
    print("="*55)

    api = login()
    if not api:
        print("Login failed.")
        return

    stocks = resolve_tokens()
    print(f"Whitelisted stocks: {len(WHITELIST)}")

    all_trades = []

    print("\nFetching history and backtesting...")
    print("-"*55)

    for i, (symbol, token) in enumerate(stocks.items(), 1):
        if symbol not in WHITELIST:
            continue

        df = fetch_full_history(api, symbol, token)
        if df is None:
            print(f"  ✗ {symbol} — no data")
            time.sleep(0.3)
            continue

        trades = backtest_stock(symbol, df)
        all_trades.extend(trades)

        wins = len([t for t in trades if t["outcome"] == "win"])
        losses = len([t for t in trades if t["outcome"] == "loss"])
        print(f"  ✓ {symbol} — {len(trades)} signals | {wins}W {losses}L")
        time.sleep(0.3)

    os.makedirs("storage", exist_ok=True)
    with open(BACKTEST_RESULTS_FILE, "w") as f:
        json.dump(all_trades, f, indent=2)

    stats = calculate_accuracy(all_trades)
    print_accuracy_report(stats, all_trades)

    with open("storage/backtest_summary.json", "w") as f:
        json.dump(stats, f, indent=2)

    print(f"\nSaved to {BACKTEST_RESULTS_FILE}")


if __name__ == "__main__":
    run_backtest()