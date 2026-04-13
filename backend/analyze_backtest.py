import json
from collections import defaultdict

with open("storage/backtest_results.json") as f:
    trades = json.load(f)

# ADX breakdown
print("ADX BREAKDOWN:")
for adx_min in [30, 33, 35, 38, 40]:
    bucket = [t for t in trades if t.get("rr", 0) >= 1.5]
    # we dont have adx in saved trades, skip

# RR breakdown
print("R/R BREAKDOWN:")
for rr_min in [1.5, 1.8, 2.0, 2.2, 2.5]:
    bucket = [t for t in trades if t["rr"] >= rr_min]
    wins = [t for t in bucket if t["outcome"] == "win"]
    if bucket:
        print(f"  RR >= {rr_min}: {len(bucket)} trades | {round(len(wins)/len(bucket)*100,1)}% WR")

# Score breakdown
print("\nSCORE BREAKDOWN:")
for score_min in [7.0, 7.5, 8.0, 8.5, 9.0]:
    bucket = [t for t in trades if t["score"] >= score_min]
    wins = [t for t in bucket if t["outcome"] == "win"]
    if bucket:
        print(f"  Score >= {score_min}: {len(bucket)} trades | {round(len(wins)/len(bucket)*100,1)}% WR")

# Monthly breakdown
print("\nMONTHLY BREAKDOWN:")
monthly = defaultdict(lambda: {"wins": 0, "total": 0})
for t in trades:
    month = t["date"][:7]
    monthly[month]["total"] += 1
    if t["outcome"] == "win":
        monthly[month]["wins"] += 1
for month in sorted(monthly.keys()):
    m = monthly[month]
    wr = round(m["wins"]/m["total"]*100,1)
    print(f"  {month}: {m['total']} trades | {wr}% WR")

# Trend + outcome
print("\nBULLISH vs BEARISH:")
for trend in ["bullish", "bearish"]:
    t_trades = [t for t in trades if t["trend"] == trend]
    t_wins = [t for t in t_trades if t["outcome"] == "win"]
    avg_win = round(sum(t["pnl_pct"] for t in t_trades if t["outcome"]=="win")/max(len(t_wins),1),2)
    avg_loss = round(sum(t["pnl_pct"] for t in t_trades if t["outcome"]=="loss")/max(len([t for t in t_trades if t["outcome"]=="loss"]),1),2)
    print(f"  {trend}: {len(t_trades)} trades | WR: {round(len(t_wins)/len(t_trades)*100,1)}% | Avg Win: +{avg_win}% | Avg Loss: {avg_loss}%")

# Best performing symbols
print("\nTOP SYMBOLS:")
stock_stats = defaultdict(lambda: {"wins":0,"total":0})
for t in trades:
    stock_stats[t["symbol"]]["total"] += 1
    if t["outcome"] == "win":
        stock_stats[t["symbol"]]["wins"] += 1
ranked = sorted(
    [(s,v["wins"],v["total"],round(v["wins"]/v["total"]*100,1))
     for s,v in stock_stats.items() if v["total"] >= 2],
    key=lambda x: x[3], reverse=True
)
for sym, wins, total, wr in ranked[:15]:
    print(f"  {sym:<15} {wins}/{total} | {wr}% WR")