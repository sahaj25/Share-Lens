"""
Backtest Runner v3 — Full 7-Layer Signal Engine
Usage: python run_backtest.py
"""

from datetime import datetime, timedelta, date
import pytz
import pandas as pd

# ── Load .env ─────────────────────────────────────────
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
from rich.rule import Rule

from angel_client import AngelOneClient, get_token
from backtester import Backtester, BacktestResult

IST     = pytz.timezone("Asia/Kolkata")
console = Console()


# ═══════════════════════════════════════════════════════
# DATA FETCHING
# ═══════════════════════════════════════════════════════

def fetch_historical(client: AngelOneClient, symbol: str,
                     from_date: date, to_date: date) -> pd.DataFrame | None:
    token, _ = get_token(symbol)

    if client.demo_mode:
        days = (to_date - from_date).days + 1
        return _generate_demo(symbol, days, anchor_date=to_date)

    try:
        params = {
            "exchange":    "NSE",
            "symboltoken": token,
            "interval":    "ONE_MINUTE",
            "fromdate":    f"{from_date} 09:15",
            "todate":      f"{to_date} 15:30",
        }
        resp = client.obj.getCandleData(params)
        if resp["status"] and resp["data"]:
            df = pd.DataFrame(resp["data"],
                              columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.set_index("timestamp").tz_convert(IST)
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(df[col])
            console.print(f"  [green]✓ {len(df)} candles fetched[/green]")
            return df
        console.print(f"  [red]API returned no data[/red]")
        return None
    except Exception as e:
        console.print(f"  [red]Fetch error: {e}[/red]")
        return None


def _generate_demo(symbol: str, days: int, anchor_date: date) -> pd.DataFrame:
    import numpy as np
    rng = np.random.default_rng(abs(hash(symbol)) % (2**32))
    anchor_dt = IST.localize(datetime.combine(anchor_date, datetime.min.time()).replace(hour=15, minute=30))
    rows = []
    base = rng.uniform(500, 3000)
    for d in range(days, 0, -1):
        day = anchor_dt - timedelta(days=d)
        if day.weekday() >= 5: continue
        start = day.replace(hour=9, minute=15, second=0, microsecond=0)
        n = 375
        drift = rng.normal(0, 0.015)
        closes = base * np.cumprod(1 + rng.normal(drift / n, 0.0018, n))
        base = closes[-1]
        for i in range(n):
            ts = start + timedelta(minutes=i)
            c = closes[i]; o = closes[i-1] if i else c
            h = max(o,c)*rng.uniform(1,1.004); l = min(o,c)*rng.uniform(0.996,1)
            rows.append({"timestamp": ts, "open": o, "high": h, "low": l,
                         "close": c, "volume": int(rng.integers(8000, 600000))})
    df = pd.DataFrame(rows).set_index("timestamp")
    df.index = pd.DatetimeIndex(df.index, tz=IST)
    return df


# ═══════════════════════════════════════════════════════
# REPORT PRINTING
# ═══════════════════════════════════════════════════════

def print_summary(result: BacktestResult):
    console.print()
    console.rule(f"[bold cyan]Backtest Results — {result.symbol}  (7-Layer Engine)[/bold cyan]")

    # ── KPI summary ───────────────────────────────────
    kpis = [
        ("Period",             f"{result.start_date} → {result.end_date}"),
        ("Trading Days",       str(result.total_days)),
        ("Total Trades",       str(result.total_trades)),
        ("Signals Blocked",    f"{result.signals_blocked}  [dim](core passed but filters blocked)[/dim]"),
        ("Win Rate",           f"{result.win_rate:.1f}%"),
        ("Total P&L",          f"₹{result.total_pnl:+.2f}"),
        ("Profit Factor",      str(result.profit_factor)),
        ("Max Drawdown",       f"₹{result.max_drawdown:.2f}"),
        ("Avg Win",            f"₹{result.avg_win:+.2f}"),
        ("Avg Loss",           f"₹{result.avg_loss:+.2f}"),
        ("Max Consec. Losses", str(result.consecutive_losses)),
    ]

    kpi_tbl = Table(box=box.SIMPLE, show_header=False, padding=(0,2))
    kpi_tbl.add_column("K", style="dim")
    kpi_tbl.add_column("V", style="bold white")
    for k, v in kpis:
        color = ""
        if "P&L" in k: color = "green" if result.total_pnl >= 0 else "red"
        kpi_tbl.add_row(k, Text.from_markup(v) if "[" in v else
                          (Text(v, style=color) if color else v))
    console.print(Panel(kpi_tbl, title="📊 Summary", border_style="cyan"))

    # ── Equity sparkline ──────────────────────────────
    if result.trades:
        equity = []
        running = 0
        for t in result.trades:
            running += t.pnl
            equity.append(running)
        spark = _sparkline(equity)
        color = "green" if equity[-1] >= 0 else "red"
        console.print(Panel(Text(spark, style=color),
                            title="📈 Equity Curve", border_style="bright_black"))

    # ── Trade log ─────────────────────────────────────
    tbl = Table(box=box.ROUNDED, border_style="bright_black",
                header_style="bold cyan", expand=True)
    tbl.add_column("Date",    width=12)
    tbl.add_column("Signal",  width=11, justify="center")
    tbl.add_column("Entry ₹", width=8,  justify="right")
    tbl.add_column("@",       width=6)
    tbl.add_column("Exit ₹",  width=8,  justify="right")
    tbl.add_column("@",       width=6)
    tbl.add_column("Qty",     width=4,  justify="right")
    tbl.add_column("SL ₹",   width=8,  justify="right")
    tbl.add_column("T2 ₹",   width=8,  justify="right")
    tbl.add_column("Core",    width=5,  justify="center")
    tbl.add_column("Filt",    width=5,  justify="center")
    tbl.add_column("VOL",     width=8,  justify="center")
    tbl.add_column("ST",      width=8,  justify="center")
    tbl.add_column("MACD",    width=10, justify="center")
    tbl.add_column("NIFTY",   width=9,  justify="center")
    tbl.add_column("Reason",  width=11)
    tbl.add_column("P&L ₹",  width=10, justify="right")
    tbl.add_column("",        width=2)

    reason_colors = {"T2_HIT": "green", "T1_HIT": "green3",
                     "SL_HIT": "red", "VWAP_EXIT": "yellow", "EOD_EXIT": "dim"}
    sig_colors    = {"BUY": "green", "SELL": "red",
                     "WEAK_BUY": "green3", "WEAK_SELL": "red3"}

    def filter_cell(v: str) -> Text:
        if v.startswith("✓"): return Text(v, style="green")
        if v.startswith("✗"): return Text(v, style="red")
        return Text(v, style="dim")

    for t in result.trades:
        pnl_style = "green" if t.pnl > 0 else "red"
        flt = t.filters
        tbl.add_row(
            t.date,
            Text(t.signal_type or t.direction, style=sig_colors.get(t.signal_type, "white")),
            f"{t.entry_price:.2f}",
            t.entry_time,
            f"{t.exit_price:.2f}",
            t.exit_time,
            str(t.qty),
            f"{t.stop_loss:.2f}",
            f"{t.target_2r:.2f}",
            Text(f"{'█'*t.confidence}{'░'*(3-t.confidence)} {t.confidence}/3",
                 style="green" if t.confidence>=2 else "yellow"),
            Text(f"{'█'*t.filter_score}{'░'*(4-t.filter_score)} {t.filter_score}/4",
                 style="green" if t.filter_score>=3 else ("yellow" if t.filter_score>=2 else "red")),
            filter_cell(flt.get("VOLUME",     "—")),
            filter_cell(flt.get("SUPERTREND", "—")),
            filter_cell(flt.get("MACD",       "—")),
            filter_cell(flt.get("NIFTY",      "—")),
            Text(t.exit_reason, style=reason_colors.get(t.exit_reason, "white")),
            Text(f"{t.pnl:+.2f}", style=pnl_style),
            Text("✓" if t.pnl > 0 else "✗", style=pnl_style),
        )

    console.print(Panel(tbl, title="📋 Trade Log", border_style="bright_black"))

    if result.best_trade and result.worst_trade:
        bt = result.best_trade; wt = result.worst_trade
        console.print(
            f"  [green]Best:[/green]  {bt.date} {bt.signal_type} → "
            f"[bold green]₹{bt.pnl:+.2f}[/bold green] ({bt.exit_reason})\n"
            f"  [red]Worst:[/red] {wt.date} {wt.signal_type} → "
            f"[bold red]₹{wt.pnl:+.2f}[/bold red] ({wt.exit_reason})"
        )

    # ── Trendiness Filter Report ──────────────────────────
    if result.trend_scores:
        console.print()
        trend_tbl = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan",
                          title="🔍 Trendiness Filter — Per-Day Scores")
        trend_tbl.add_column("Date",        width=12)
        trend_tbl.add_column("Score",       width=8,  justify="center")
        trend_tbl.add_column("Decision",    width=14, justify="center")
        trend_tbl.add_column("Direction",   width=10, justify="center")
        trend_tbl.add_column("Net Move",    width=12, justify="center")
        trend_tbl.add_column("Consistency", width=14, justify="center")
        trend_tbl.add_column("Volatility",  width=14, justify="center")
        trend_tbl.add_column("Volume",      width=16, justify="center")

        for date_str, ts in sorted(result.trend_scores.items()):
            d = ts.get("details", {})
            passed = ts["pass"]
            trend_tbl.add_row(
                date_str,
                Text(f"{ts['score']}/4", style="green" if passed else "red"),
                Text("✅ TRADE" if passed else "⛔ SKIP", style="green" if passed else "red"),
                Text(d.get("direction", "?"), style="green" if d.get("direction") == "UP" else "red"),
                Text(d.get("net_move", "—"), style="green" if "✓" in d.get("net_move","") else "red"),
                Text(d.get("consistency", "—"), style="green" if "✓" in d.get("consistency","") else "red"),
                Text(d.get("volatility", "—"), style="green" if "✓" in d.get("volatility","") else "red"),
                Text(d.get("volume_trend", "—"), style="green" if "✓" in d.get("volume_trend","") else "dim"),
            )

        console.print(Panel(trend_tbl, border_style="bright_black"))
        console.print(
            f"  [dim]Days traded: {result.days_traded_by_trend}  │  "
            f"Days skipped: {result.days_skipped_by_trend}[/dim]"
        )

    console.print()


def _sparkline(values: list, width: int = 60) -> str:
    blocks = "▁▂▃▄▅▆▇█"
    if not values or max(values) == min(values): return "─" * width
    mn, mx = min(values), max(values)
    step = (mx - mn) / (len(blocks) - 1)
    sampled = values if len(values) <= width else [
        values[int(i * len(values) / width)] for i in range(width)]
    return "".join(blocks[min(int((v - mn) / step), len(blocks)-1)] for v in sampled)


# ═══════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════

def last_friday() -> date:
    today = date.today()
    return today - timedelta(days=(today.weekday() - 4) % 7 or 7)

def parse_date(s: str) -> date:
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try: return datetime.strptime(s.strip(), fmt).date()
        except ValueError: pass
    raise ValueError(f"Cannot parse date: {s!r}  (use YYYY-MM-DD)")


# ═══════════════════════════════════════════════════════
# SETUP & MAIN
# ═══════════════════════════════════════════════════════

def setup():
    console.print(Panel(
        "[bold cyan]Backtest Runner v3 — Full 7-Layer Engine[/bold cyan]\n"
        "[dim]ORB + VWAP + RSI + Volume + Supertrend + MACD + Nifty MTF[/dim]",
        border_style="cyan"
    ))

    # Load .env credentials
    api_key     = os.getenv("ANGEL_API_KEY")
    client_id   = os.getenv("ANGEL_CLIENT_ID")
    password    = os.getenv("ANGEL_PASSWORD")
    totp_secret = os.getenv("ANGEL_TOTP_SECRET")
    env_loaded  = all([api_key, client_id, password, totp_secret])

    if env_loaded:
        console.print(f"\n[green]✓ Credentials loaded from .env[/green] (Client: {client_id})")
        client = AngelOneClient(api_key, client_id, password, totp_secret)
        with console.status("[cyan]Connecting..."):
            ok, msg = client.connect()
        if ok:
            console.print(f"[green]✓ {msg}[/green]")
        else:
            console.print(f"[red]✗ {msg} — DEMO fallback[/red]")
            client.demo_mode = True; client.connected = True
    else:
        use_demo = Confirm.ask("\n[yellow]Demo mode?[/yellow]", default=True)
        if use_demo:
            client = AngelOneClient("DEMO","DEMO","DEMO","DEMO")
            client.connected = True; client.demo_mode = True
        else:
            api_key     = Prompt.ask("API Key")
            client_id   = Prompt.ask("Client ID")
            password    = Prompt.ask("Password", password=True)
            totp_secret = Prompt.ask("TOTP Secret")
            client = AngelOneClient(api_key, client_id, password, totp_secret)
            with console.status("[cyan]Connecting..."):
                ok, msg = client.connect()
            console.print(f"[{'green' if ok else 'red'}]{'✓' if ok else '✗'} {msg}[/]")
            if not ok:
                client.demo_mode = True; client.connected = True

    raw     = Prompt.ask("\nSymbols to backtest (comma separated)", default="ADANIPOWER")
    symbols = [s.strip().upper() for s in raw.split(",") if s.strip()]

    lf = last_friday()
    console.print(f"\n[bold]Date range[/bold]  [dim](last Friday = {lf})[/dim]")
    from_str = Prompt.ask("From date", default=str(lf))
    to_str   = Prompt.ask("To date",   default=str(lf))
    try:
        from_date = parse_date(from_str)
        to_date   = parse_date(to_str)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        from_date = to_date = lf
    if from_date > to_date:
        from_date, to_date = to_date, from_date
    console.print(f"  [cyan]Range: {from_date} → {to_date}[/cyan]")

    capital = float(Prompt.ask("\nCapital (₹)", default="5000"))

    use_trend = Confirm.ask(
        "\n[cyan]Enable trendiness pre-filter?[/cyan] "
        "(skips choppy/flat stocks on days they don\'t qualify)",
        default=True
    )

    return client, symbols, from_date, to_date, capital, use_trend


def main():
    client, symbols, from_date, to_date, capital, use_trend = setup()
    bt = Backtester(capital=capital, max_trades_per_day=2,
                    trend_filter=use_trend, trend_min_score=2, trend_lookback_days=3)
    if use_trend:
        console.print("  [cyan]Trendiness filter: ON[/cyan] (score ≥ 2/4 required per day)")
    else:
        console.print("  [yellow]Trendiness filter: OFF[/yellow]")

    # Fetch Nifty once for MTF filter
    console.print("\n[cyan]Fetching Nifty data for MTF filter...[/cyan]")
    try:
        nifty_df = fetch_historical(client, "NIFTY", from_date=from_date, to_date=to_date)
        if nifty_df is not None and not nifty_df.empty:
            nifty_df = nifty_df[(nifty_df.index.date >= from_date) &
                                (nifty_df.index.date <= to_date)]
            console.print(f"  [green]✓ Nifty: {len(nifty_df)} candles[/green]")
        else:
            nifty_df = None
            console.print("  [yellow]⚠ Nifty unavailable — MTF filter skipped[/yellow]")
    except Exception as e:
        nifty_df = None
        console.print(f"  [yellow]⚠ Nifty fetch failed ({e}) — MTF skipped[/yellow]")

    for sym in symbols:
        console.print(f"\n[cyan]Fetching {sym}  {from_date} → {to_date}...[/cyan]")
        try:
            df = fetch_historical(client, sym, from_date=from_date, to_date=to_date)
        except ValueError as e:
            console.print(f"[red]✗ {e}[/red]"); continue

        if df is None or df.empty:
            console.print(f"[red]No data for {sym}[/red]"); continue

        df = df[(df.index.date >= from_date) & (df.index.date <= to_date)]
        if df.empty:
            console.print(f"[yellow]No candles in range[/yellow]"); continue

        console.print(f"  [dim]{len(df)} candles — running 7-layer backtest...[/dim]")
        with console.status(f"[cyan]Backtesting {sym}..."):
            result = bt.run(df, sym, nifty_df=nifty_df)

        print_summary(result)

    console.print("[bold green]Backtest complete.[/bold green]")


if __name__ == "__main__":
    main()