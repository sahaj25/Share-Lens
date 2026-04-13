"""
Intraday Signal Dashboard v2
Rich terminal UI — 7-layer confirmation display
Usage: python dashboard.py
"""

import time
from datetime import datetime
import pytz

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich import box
from rich.prompt import Prompt, Confirm

from signal_engine import analyse_symbol
from angel_client import AngelOneClient, get_token

IST = pytz.timezone("Asia/Kolkata")
console = Console()

REFRESH_SECONDS = 60
INTERVAL        = "ONE_MINUTE"
NIFTY_SYMBOL    = "NIFTY"


# ═══════════════════════════════════════════════
# UI HELPERS
# ═══════════════════════════════════════════════

def signal_color(sig: str) -> str:
    if sig == "BUY":        return "bold green"
    if sig == "WEAK_BUY":   return "bold green3"
    if sig == "SELL":       return "bold red"
    if sig == "WEAK_SELL":  return "bold red3"
    return "yellow"

def signal_label(sig: str) -> str:
    return {"BUY": "BUY ✅", "SELL": "SELL 🔴",
            "WEAK_BUY": "~BUY⚠", "WEAK_SELL": "~SELL⚠",
            "WAIT": "WAIT"}.get(sig, sig)

def confidence_bar(n: int, total: int = 3) -> str:
    return "█" * n + "░" * (total - n)

def strategy_badge(sv: str) -> Text:
    MAP = {
        "BUY":          ("BUY",   "green"),
        "SELL":         ("SELL",  "red"),
        "NEUTRAL":      ("──",    "dim"),
        "IN_RANGE":     ("RNG",   "cyan"),
        "NOT_FORMED":   ("…",     "dim"),
    }
    label, color = MAP.get(sv, (sv[:4], "white"))
    return Text(label, style=color)

def filter_text(fval: str) -> Text:
    if fval.startswith("✓"):  return Text(fval, style="green")
    if fval.startswith("✗"):  return Text(fval, style="red")
    if fval.startswith("?"):  return Text(fval, style="dim")
    return Text(fval, style="yellow")

def nifty_badge(trend: str) -> Text:
    colors = {"BULLISH": "green", "BEARISH": "red", "NEUTRAL": "yellow", "UNKNOWN": "dim"}
    return Text(trend, style=colors.get(trend, "white"))


# ═══════════════════════════════════════════════
# TABLE BUILDER
# ═══════════════════════════════════════════════

def build_signal_table(results: list, nifty_trend: str = "UNKNOWN") -> Table:
    table = Table(
        box=box.ROUNDED,
        border_style="bright_black",
        header_style="bold cyan",
        expand=True,
    )

    # ── Columns ───────────────────────────────
    table.add_column("Symbol",    style="bold white", width=10)
    table.add_column("LTP ₹",    justify="right",    width=9)
    table.add_column("Signal",   justify="center",   width=10)
    table.add_column("Core",     justify="center",   width=8)   # 3 strategy votes
    table.add_column("Filters",  justify="center",   width=8)   # 4 filter score
    table.add_column("VOL",      justify="center",   width=7)
    table.add_column("ST",       justify="center",   width=8)
    table.add_column("MACD",     justify="center",   width=10)
    table.add_column("NIFTY",    justify="center",   width=9)
    table.add_column("RSI",      justify="right",    width=6)
    table.add_column("ORB",      justify="center",   width=12)
    table.add_column("SL ₹",    justify="right",    width=8)
    table.add_column("T1 ₹",    justify="right",    width=8)
    table.add_column("T2 ₹",    justify="right",    width=8)
    table.add_column("Qty",      justify="right",    width=4)

    for r in results:
        if "error" in r:
            table.add_row(r["symbol"], "—", Text("ERROR","red"), *["—"]*12)
            continue

        sig   = r["signal"]
        price = r["price"]
        orb   = r["orb"]
        flt   = r.get("filters", {})
        risk  = r.get("risk", {})

        # ORB
        if orb and orb["formed"]:
            orb_txt = Text(f"{orb['low']:.1f}–{orb['high']:.1f}", style="cyan")
        elif orb:
            orb_txt = Text("Forming…", style="dim")
        else:
            orb_txt = Text("Pre-ORB", style="dim")

        # Core strategy badge
        core_bar = Text(
            f"{confidence_bar(r['confidence'])} {r['confidence']}/3",
            style="green" if r["confidence"] >= 2 else "yellow"
        )

        # Filter score badge
        fs = r.get("filter_score", 0)
        filter_bar = Text(
            f"{confidence_bar(fs, 4)} {fs}/4",
            style="green" if fs >= 3 else ("yellow" if fs >= 2 else "red")
        )

        table.add_row(
            r["symbol"],
            f"{price:,.2f}" if price else "—",
            Text(signal_label(sig), style=signal_color(sig)),
            core_bar,
            filter_bar,
            filter_text(flt.get("VOLUME",     "SKIP")),
            filter_text(flt.get("SUPERTREND", "SKIP")),
            filter_text(flt.get("MACD",       "SKIP")),
            filter_text(flt.get("NIFTY",      "SKIP")),
            f"{r['rsi']:.1f}" if r.get("rsi") else "—",
            orb_txt,
            str(risk.get("stop_loss_price", "—")),
            str(risk.get("target_1R",       "—")),
            str(risk.get("target_2R",       "—")),
            str(risk.get("suggested_qty",   "—")),
        )

    return table


def build_legend_panel(nifty_trend: str) -> Panel:
    t = Text()
    t.append("⚡ ", style="yellow")
    t.append("1% rule  ", style="dim")
    t.append("│ ", style="bright_black")
    t.append("Signal = Core≥2 AND Vol✓ AND ST✓ AND MACD✓  ", style="bold cyan")
    t.append("│ ", style="bright_black")
    t.append("~WEAK = Nifty against  ", style="yellow")
    t.append("│ ", style="bright_black")
    t.append("Nifty: ", style="dim")
    t.append_text(nifty_badge(nifty_trend))
    t.append("  │ ", style="bright_black")
    t.append("Stop after 2 losses", style="red")
    return Panel(t, border_style="bright_black", padding=(0, 1))


def build_header(mode: str, capital: float, countdown: int | None = None) -> Panel:
    now = datetime.now(IST).strftime("%d %b %Y  %H:%M:%S IST")
    t = Text()
    t.append("📈 SIGNAL ENGINE v2  ", style="bold bright_white")
    t.append(f"  {now}  ", style="dim")
    t.append(f"  ₹{capital:,.0f}  ", style="cyan")
    t.append(f"  {mode}", style="yellow" if "DEMO" in mode else "green")
    if countdown is not None:
        t.append(f"  │  refresh in {countdown}s", style="dim")
    return Panel(t, border_style="cyan", padding=(0, 1))


# ═══════════════════════════════════════════════
# SETUP WIZARD
# ═══════════════════════════════════════════════

def setup_wizard():
    console.print(Panel(
        "[bold cyan]Intraday Signal Engine v2[/bold cyan]\n"
        "[dim]7-layer confirmation: ORB + VWAP + RSI + Volume + Supertrend + MACD + Nifty[/dim]",
        border_style="cyan"
    ))

    use_demo = Confirm.ask("\n[yellow]Demo mode?[/yellow] (synthetic data, no API)", default=True)

    if use_demo:
        client   = AngelOneClient("DEMO", "DEMO", "DEMO", "DEMO")
        client.connected  = True
        client.demo_mode  = True
        mode_str = "DEMO MODE"
    else:
        console.print("\n[bold]Angel One credentials:[/bold]")
        api_key     = Prompt.ask("API Key")
        client_id   = Prompt.ask("Client ID")
        password    = Prompt.ask("Password", password=True)
        totp_secret = Prompt.ask("TOTP Secret")

        client = AngelOneClient(api_key, client_id, password, totp_secret)
        with console.status("[cyan]Connecting..."):
            ok, msg = client.connect()

        if ok:
            console.print(f"[green]✓ {msg}[/green]")
            mode_str = "LIVE"
        else:
            console.print(f"[red]✗ {msg} — falling back to DEMO[/red]")
            client.demo_mode = True
            client.connected = True
            mode_str = "DEMO MODE"

    console.print("\n[bold]Symbols to track[/bold] (any NSE symbol — e.g. OLAELEC,SUZLON,TCS)")
    raw     = Prompt.ask("Symbols", default="RELIANCE,TCS")
    symbols = [s.strip().upper() for s in raw.split(",") if s.strip()]

    capital = float(Prompt.ask("\nCapital (₹)", default="5000"))
    return client, symbols, capital, mode_str


# ═══════════════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════════════

def run():
    client, symbols, capital, mode_str = setup_wizard()
    console.print(f"\n[green]Tracking:[/green] {', '.join(symbols)}  +  Nifty (auto)")
    console.print(f"[dim]Refreshing every {REFRESH_SECONDS}s. Ctrl+C to quit.[/dim]\n")
    time.sleep(1)

    nifty_trend = "UNKNOWN"

    with Live(console=console, refresh_per_second=1, screen=True) as live:
        while True:
            # ── Fetch Nifty for MTF context ────────
            try:
                nifty_token, _ = get_token(NIFTY_SYMBOL)
                nifty_df = client.get_candles(nifty_token, NIFTY_SYMBOL, INTERVAL, lookback_minutes=120)
            except Exception:
                nifty_df = None

            # ── Fetch & analyse each symbol ────────
            results = []
            for sym in symbols:
                try:
                    token, full_name = get_token(sym)
                except ValueError as e:
                    results.append({
                        "symbol": sym, "signal": "WAIT", "confidence": 0,
                        "filter_score": 0, "strategies": {}, "filters": {},
                        "blocked_by": [], "price": None, "vwap": None,
                        "rsi": None, "ema9": None, "orb": None, "risk": {},
                        "volume_spike": False, "supertrend": None, "macd": None,
                        "nifty_trend": "UNKNOWN",
                        "error": str(e).split("\n")[0]
                    })
                    continue

                df = client.get_candles(token, sym, INTERVAL, lookback_minutes=180)
                result = analyse_symbol(df, sym, capital, nifty_df=nifty_df)
                result["full_name"] = full_name
                results.append(result)

            # Pull nifty_trend from first result (all share same nifty_df)
            if results:
                nifty_trend = results[0].get("nifty_trend", "UNKNOWN")

            # ── Build layout ───────────────────────
            layout = Layout()
            layout.split_column(
                Layout(name="header", size=3),
                Layout(name="main"),
                Layout(name="footer", size=3),
            )
            layout["header"].update(build_header(mode_str, capital))
            layout["main"].update(build_signal_table(results, nifty_trend))
            layout["footer"].update(build_legend_panel(nifty_trend))
            live.update(layout)

            # ── Countdown ─────────────────────────
            for remaining in range(REFRESH_SECONDS, 0, -1):
                time.sleep(1)
                layout["header"].update(build_header(mode_str, capital, countdown=remaining))
                live.update(layout)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        console.print("\n[yellow]Exited. Trade safe! 🙏[/yellow]")