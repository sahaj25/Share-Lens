"""
Backtest Runner — fetches historical data from Angel One and runs the backtester
Usage: python run_backtest.py
"""

import sys
import time
from datetime import datetime, timedelta, date
import pytz
import pandas as pd

# ── Load .env ─────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
import os

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich import box
from rich.columns import Columns
from rich.rule import Rule

from angel_client import AngelOneClient, get_token
from backtester import Backtester, BacktestResult, Trade

IST = pytz.timezone("Asia/Kolkata")
console = Console()


# ─────────────────────────────────────────
# Data Fetching (historical)
# ─────────────────────────────────────────

def fetch_historical(client: AngelOneClient, symbol: str,
                     from_date: date | None = None,
                     to_date: date | None = None,
                     days: int = 30) -> pd.DataFrame | None:
    """
    Fetch 1-min candle data for a date range.
    from_date / to_date override the days parameter when provided.
    Angel One max: 30 days per ONE_MINUTE request.
    """
    token, _ = get_token(symbol)

    now = datetime.now(IST)
    if to_date is None:
        to_date = now.date()
    if from_date is None:
        from_date = (now - timedelta(days=min(days, 29))).date()

    if client.demo_mode:
        days_requested = (to_date - from_date).days + 1
        return _generate_multi_day_demo(symbol, days_requested, anchor_date=to_date)

    try:
        from SmartApi import SmartConnect

        params = {
            "exchange": "NSE",
            "symboltoken": token,
            "interval": "ONE_MINUTE",
            "fromdate": f"{from_date} 09:15",
            "todate":   f"{to_date} 15:30",
        }
        resp = client.obj.getCandleData(params)
        if resp["status"] and resp["data"]:
            df = pd.DataFrame(resp["data"],
                              columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.set_index("timestamp").tz_convert(IST)
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(df[col])
            console.print(f"[green]✓ Fetched {len(df)} candles for {symbol}[/green]")
            return df
        else:
            console.print(f"[red]API returned no data for {symbol}[/red]")
            return None
    except Exception as e:
        console.print(f"[red]Error fetching {symbol}: {e}[/red]")
        return None


def _generate_multi_day_demo(symbol: str, days: int = 30,
                              anchor_date=None) -> pd.DataFrame:
    """Synthetic multi-day 1-min data for demo backtesting"""
    import numpy as np
    rng = np.random.default_rng(abs(hash(symbol)) % (2**32))

    if anchor_date is None:
        anchor_date = datetime.now(IST).date()
    anchor_dt = datetime.combine(anchor_date, __import__('datetime').time(15, 30))
    anchor_dt = IST.localize(anchor_dt)
    all_rows = []

    base_price = rng.uniform(500, 3000)
    # Simulate persistent price drift across days
    for d in range(days, 0, -1):
        day = anchor_dt - timedelta(days=d)
        if day.weekday() >= 5:   # skip weekends
            continue

        start = day.replace(hour=9, minute=15, second=0, microsecond=0)
        candles_per_day = 375   # 9:15 to 15:29 inclusive

        daily_drift = rng.normal(0, 0.015)
        returns = rng.normal(daily_drift / candles_per_day, 0.0018, candles_per_day)
        closes = base_price * np.cumprod(1 + returns)
        base_price = closes[-1]   # next day opens near today's close

        for i in range(candles_per_day):
            ts = start + timedelta(minutes=i)
            c = closes[i]
            o = closes[i - 1] if i > 0 else c * rng.uniform(0.999, 1.001)
            h = max(o, c) * rng.uniform(1.0, 1.004)
            l = min(o, c) * rng.uniform(0.996, 1.0)
            v = int(rng.integers(8000, 600000))
            all_rows.append({"timestamp": ts, "open": o, "high": h, "low": l, "close": c, "volume": v})

    df = pd.DataFrame(all_rows).set_index("timestamp")
    df.index = pd.DatetimeIndex(df.index, tz=IST)
    return df


# ─────────────────────────────────────────
# Rich Report
# ─────────────────────────────────────────

def print_summary(result: BacktestResult):
    console.print()
    console.rule(f"[bold cyan]Backtest Results — {result.symbol}[/bold cyan]")

    # ── KPI Panel ─────────────────────────
    kpis = [
        ("Period", f"{result.start_date} → {result.end_date}"),
        ("Trading Days", str(result.total_days)),
        ("Total Trades", str(result.total_trades)),
        ("Win Rate", f"{result.win_rate:.1f}%"),
        ("Total P&L", f"₹{result.total_pnl:+.2f}"),
        ("Profit Factor", str(result.profit_factor)),
        ("Max Drawdown", f"₹{result.max_drawdown:.2f}"),
        ("Avg Win", f"₹{result.avg_win:+.2f}"),
        ("Avg Loss", f"₹{result.avg_loss:+.2f}"),
        ("Max Consec. Losses", str(result.consecutive_losses)),
    ]

    kpi_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    kpi_table.add_column("Metric", style="dim")
    kpi_table.add_column("Value", style="bold white")
    for k, v in kpis:
        color = ""
        if "P&L" in k:
            color = "green" if result.total_pnl >= 0 else "red"
        kpi_table.add_row(k, Text(v, style=color) if color else v)

    console.print(Panel(kpi_table, title="📊 Summary", border_style="cyan"))

    # ── Equity Curve (ASCII sparkline) ────
    if result.trades:
        equity = []
        running = 0
        for t in result.trades:
            running += t.pnl
            equity.append(running)

        sparkline = build_sparkline(equity, width=60)
        color = "green" if equity[-1] >= 0 else "red"
        console.print(Panel(
            Text(sparkline, style=color),
            title="📈 Equity Curve",
            border_style="bright_black"
        ))

    # ── Per-Trade Table ───────────────────
    trade_table = Table(
        box=box.ROUNDED,
        border_style="bright_black",
        header_style="bold cyan",
        expand=True,
    )
    trade_table.add_column("Date", width=12)
    trade_table.add_column("Dir", width=6, justify="center")
    trade_table.add_column("Entry", justify="right", width=8)
    trade_table.add_column("Entry@", width=7)
    trade_table.add_column("Exit", justify="right", width=8)
    trade_table.add_column("Exit@", width=7)
    trade_table.add_column("Qty", justify="right", width=5)
    trade_table.add_column("SL ₹", justify="right", width=8)
    trade_table.add_column("T2 ₹", justify="right", width=8)
    trade_table.add_column("Reason", width=10)
    trade_table.add_column("Conf", width=6, justify="center")
    trade_table.add_column("P&L ₹", justify="right", width=10)
    trade_table.add_column("", width=2)   # Win/loss icon

    for t in result.trades:
        pnl_style = "green" if t.pnl > 0 else "red"
        dir_style = "green" if t.direction == "BUY" else "red"
        icon = "✓" if t.pnl > 0 else "✗"
        reason_colors = {
            "T2_HIT": "green", "T1_HIT": "green3",
            "SL_HIT": "red", "EOD_EXIT": "yellow"
        }
        trade_table.add_row(
            t.date,
            Text(t.direction, style=dir_style),
            f"{t.entry_price:.2f}",
            t.entry_time,
            f"{t.exit_price:.2f}",
            t.exit_time,
            str(t.qty),
            f"{t.stop_loss:.2f}",
            f"{t.target_2r:.2f}",
            Text(t.exit_reason, style=reason_colors.get(t.exit_reason, "white")),
            "█" * t.confidence + "░" * (3 - t.confidence),
            Text(f"{t.pnl:+.2f}", style=pnl_style),
            Text(icon, style=pnl_style),
        )

    console.print(Panel(trade_table, title="📋 Trade Log", border_style="bright_black"))

    # ── Best / Worst ──────────────────────
    if result.best_trade and result.worst_trade:
        bt = result.best_trade
        wt = result.worst_trade
        console.print(
            f"  [green]Best trade:[/green]  {bt.date} {bt.direction} {bt.symbol} → "
            f"[bold green]₹{bt.pnl:+.2f}[/bold green] ({bt.exit_reason})\n"
            f"  [red]Worst trade:[/red] {wt.date} {wt.direction} {wt.symbol} → "
            f"[bold red]₹{wt.pnl:+.2f}[/bold red] ({wt.exit_reason})"
        )

    console.print()


def build_sparkline(values: list, width: int = 60) -> str:
    """ASCII sparkline from equity values"""
    blocks = "▁▂▃▄▅▆▇█"
    if not values or max(values) == min(values):
        return "─" * width

    mn, mx = min(values), max(values)
    step = (mx - mn) / (len(blocks) - 1) if mx != mn else 1

    # Sample to fit width
    sampled = values if len(values) <= width else [
        values[int(i * len(values) / width)] for i in range(width)
    ]
    return "".join(blocks[min(int((v - mn) / step), len(blocks) - 1)] for v in sampled)


# ─────────────────────────────────────────
# Setup & Main
# ─────────────────────────────────────────

def setup():
    console.print(Panel(
        "[bold cyan]Backtest Runner[/bold cyan]\n"
        "[dim]Replays historical candle data through ORB + VWAP + RSI engine[/dim]",
        border_style="cyan"
    ))

    use_demo = Confirm.ask("\nRun in DEMO mode? (synthetic historical data)", default=True)

    if use_demo:
        client = AngelOneClient("DEMO", "DEMO", "DEMO", "DEMO")
        client.connected = True
        client.demo_mode = True
    else:
        console.print("\n[bold]Angel One SmartAPI credentials:[/bold]")
        api_key = Prompt.ask("API Key")
        client_id = Prompt.ask("Client ID")
        password = Prompt.ask("Password", password=True)
        totp_secret = Prompt.ask("TOTP Secret")

        client = AngelOneClient(api_key, client_id, password, totp_secret)
        with console.status("[cyan]Connecting..."):
            ok, msg = client.connect()
        if ok:
            console.print(f"[green]✓ {msg}[/green]")
        else:
            console.print(f"[red]✗ {msg} — falling back to demo[/red]")
            client.demo_mode = True
            client.connected = True

    raw = Prompt.ask("\nSymbols to backtest (comma separated)", default="RELIANCE,TCS")
    symbols = [s.strip().upper() for s in raw.split(",") if s.strip()]

    days = int(Prompt.ask("Days of history to backtest", default="30"))
    capital = float(Prompt.ask("Capital (₹)", default="5000"))

    return client, symbols, days, capital


def main():
    client, symbols, days, capital = setup()
    bt = Backtester(capital=capital, max_trades_per_day=2)

    for sym in symbols:
        console.print(f"\n[cyan]Fetching data for {sym}...[/cyan]")
        try:
            df = fetch_historical(client, sym, days=days)
        except ValueError as e:
            console.print(f"[red]✗ {e}[/red]")
            continue

        if df is None or df.empty:
            console.print(f"[red]No data for {sym}, skipping.[/red]")
            continue

        console.print(f"[dim]Running backtest on {len(df)} candles...[/dim]")
        with console.status(f"[cyan]Backtesting {sym}..."):
            result = bt.run(df, sym)

        print_summary(result)

    console.print("[dim]Backtest complete.[/dim]")


if __name__ == "__main__":
    main()