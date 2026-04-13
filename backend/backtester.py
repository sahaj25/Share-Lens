"""
Backtester for Intraday Signal Engine
Replays historical 1-min candle data through ORB + VWAP + RSI strategies
Simulates realistic trade execution with SL and target hits
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import pytz
from dataclasses import dataclass, field
from typing import Optional

IST = pytz.timezone("Asia/Kolkata")

# ── Reuse indicator functions from signal_engine ──
from signal_engine import calculate_vwap, calculate_ema, calculate_rsi


# ─────────────────────────────────────────
# Data Structures
# ─────────────────────────────────────────

@dataclass
class Trade:
    date: str
    symbol: str
    direction: str          # BUY / SELL
    entry_time: str
    entry_price: float
    stop_loss: float
    target_1r: float
    target_2r: float
    exit_price: float = 0.0
    exit_time: str = ""
    exit_reason: str = ""   # SL_HIT / T1_HIT / T2_HIT / EOD_EXIT
    pnl: float = 0.0
    qty: int = 1
    confidence: int = 0
    strategies: dict = field(default_factory=dict)


@dataclass
class BacktestResult:
    symbol: str
    start_date: str
    end_date: str
    total_days: int
    trades: list
    capital: float

    @property
    def total_trades(self): return len(self.trades)

    @property
    def wins(self): return [t for t in self.trades if t.pnl > 0]

    @property
    def losses(self): return [t for t in self.trades if t.pnl <= 0]

    @property
    def win_rate(self):
        return (len(self.wins) / self.total_trades * 100) if self.total_trades else 0

    @property
    def total_pnl(self): return sum(t.pnl for t in self.trades)

    @property
    def max_drawdown(self):
        if not self.trades:
            return 0
        equity = []
        running = 0
        for t in self.trades:
            running += t.pnl
            equity.append(running)
        peak = equity[0]
        max_dd = 0
        for e in equity:
            if e > peak:
                peak = e
            dd = peak - e
            if dd > max_dd:
                max_dd = dd
        return max_dd

    @property
    def profit_factor(self):
        gross_profit = sum(t.pnl for t in self.wins)
        gross_loss = abs(sum(t.pnl for t in self.losses))
        return round(gross_profit / gross_loss, 2) if gross_loss > 0 else float("inf")

    @property
    def avg_win(self):
        return (sum(t.pnl for t in self.wins) / len(self.wins)) if self.wins else 0

    @property
    def avg_loss(self):
        return (sum(t.pnl for t in self.losses) / len(self.losses)) if self.losses else 0

    @property
    def best_trade(self):
        return max(self.trades, key=lambda t: t.pnl) if self.trades else None

    @property
    def worst_trade(self):
        return min(self.trades, key=lambda t: t.pnl) if self.trades else None

    @property
    def consecutive_losses(self):
        max_streak = streak = 0
        for t in self.trades:
            if t.pnl <= 0:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0
        return max_streak


# ─────────────────────────────────────────
# Signal Logic (candle-by-candle replay)
# ─────────────────────────────────────────

def get_orb_from_slice(df_slice: pd.DataFrame):
    """Get ORB from the first 15 candles of the day (9:15–9:29)"""
    orb = df_slice.between_time("09:15", "09:29")
    if orb.empty:
        return None
    return {"high": float(orb["high"].max()), "low": float(orb["low"].min())}


def generate_signal_at_candle(df_upto: pd.DataFrame) -> dict:
    """
    Run the triple strategy on data up to (but not including) current candle.
    Returns signal dict.
    """
    if len(df_upto) < 20:
        return {"signal": "WAIT", "confidence": 0, "strategies": {}}

    df = df_upto.copy()
    df["vwap"] = calculate_vwap(df)
    df["ema9"] = calculate_ema(df["close"], 9)
    df["rsi"] = calculate_rsi(df["close"], 14)

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    price = float(latest["close"])
    vwap = float(latest["vwap"])
    ema9 = float(latest["ema9"])
    rsi = float(latest["rsi"])
    prev_rsi = float(prev["rsi"])

    bullish = bearish = 0
    strats = {}

    # VWAP
    if price > vwap and ema9 > vwap:
        strats["VWAP"] = "BUY"; bullish += 1
    elif price < vwap and ema9 < vwap:
        strats["VWAP"] = "SELL"; bearish += 1
    else:
        strats["VWAP"] = "NEUTRAL"

    # RSI
    if float(prev["rsi"]) < 30 and rsi > prev_rsi:
        strats["RSI"] = "BUY"; bullish += 1
    elif float(prev["rsi"]) > 70 and rsi < prev_rsi:
        strats["RSI"] = "SELL"; bearish += 1
    else:
        strats["RSI"] = "NEUTRAL"

    # ORB
    orb = get_orb_from_slice(df)
    if orb:
        if price > orb["high"]:
            strats["ORB"] = "BUY"; bullish += 1
        elif price < orb["low"]:
            strats["ORB"] = "SELL"; bearish += 1
        else:
            strats["ORB"] = "IN_RANGE"
    else:
        strats["ORB"] = "NOT_FORMED"

    confidence = max(bullish, bearish)
    if bullish >= 2:
        signal = "BUY"
    elif bearish >= 2:
        signal = "SELL"
    else:
        signal = "WAIT"

    return {
        "signal": signal,
        "confidence": confidence,
        "strategies": strats,
        "price": price,
        "vwap": vwap,
        "rsi": rsi,
        "orb": orb,
    }


# ─────────────────────────────────────────
# Core Backtester
# ─────────────────────────────────────────

class Backtester:
    def __init__(self, capital: float = 5000.0, max_trades_per_day: int = 2):
        self.capital = capital
        self.max_trades_per_day = max_trades_per_day
        self.max_loss_per_trade = capital * 0.01   # 1% rule

    def run(self, df: pd.DataFrame, symbol: str) -> BacktestResult:
        """
        df: Full historical 1-min OHLCV DataFrame with DatetimeIndex (IST)
        """
        df = df.copy()
        if not hasattr(df.index, "date"):
            df.index = pd.to_datetime(df.index)
        if df.index.tzinfo is None:
            df.index = df.index.tz_localize(IST)
        else:
            df.index = df.index.tz_convert(IST)

        trading_days = sorted(set(df.index.date))
        all_trades = []

        for day in trading_days:
            day_df = df[df.index.date == day]
            # Filter market hours 9:15 to 15:30
            day_df = day_df.between_time("09:15", "15:30")
            if len(day_df) < 20:
                continue

            trades_today = self._simulate_day(day_df, symbol, str(day))
            all_trades.extend(trades_today)

        return BacktestResult(
            symbol=symbol,
            start_date=str(trading_days[0]) if trading_days else "—",
            end_date=str(trading_days[-1]) if trading_days else "—",
            total_days=len(trading_days),
            trades=all_trades,
            capital=self.capital,
        )

    def _simulate_day(self, day_df: pd.DataFrame, symbol: str, day_str: str) -> list:
        trades = []
        in_trade = False
        trade_count = 0
        current_trade: Optional[Trade] = None

        candles = list(day_df.iterrows())

        for i, (ts, candle) in enumerate(candles):
            # ── Check open trade for SL / Target hit ──
            if in_trade and current_trade:
                hi = float(candle["high"])
                lo = float(candle["low"])
                t = current_trade

                hit = None
                if t.direction == "BUY":
                    if lo <= t.stop_loss:
                        hit = ("SL_HIT", t.stop_loss)
                    elif hi >= t.target_2r:
                        hit = ("T2_HIT", t.target_2r)
                    elif hi >= t.target_1r:
                        hit = ("T1_HIT", t.target_1r)
                else:  # SELL
                    if hi >= t.stop_loss:
                        hit = ("SL_HIT", t.stop_loss)
                    elif lo <= t.target_2r:
                        hit = ("T2_HIT", t.target_2r)
                    elif lo <= t.target_1r:
                        hit = ("T1_HIT", t.target_1r)

                # EOD exit at 15:15
                if not hit and ts.time() >= time_obj(15, 15):
                    hit = ("EOD_EXIT", float(candle["close"]))

                if hit:
                    reason, exit_px = hit
                    t.exit_price = exit_px
                    t.exit_time = ts.strftime("%H:%M")
                    t.exit_reason = reason
                    if t.direction == "BUY":
                        t.pnl = (exit_px - t.entry_price) * t.qty
                    else:
                        t.pnl = (t.entry_price - exit_px) * t.qty
                    trades.append(t)
                    in_trade = False
                    current_trade = None
                continue

            # ── Look for new signal (only if not in trade) ──
            if in_trade or trade_count >= self.max_trades_per_day:
                continue

            # Only look for signals after ORB is formed (9:30+)
            if ts.time() < time_obj(9, 30):
                continue

            df_upto = day_df.iloc[: i + 1]
            sig = generate_signal_at_candle(df_upto)

            if sig["signal"] in ("BUY", "SELL"):
                price = float(candle["close"])
                orb = sig.get("orb")

                # Determine SL
                if orb:
                    sl = orb["low"] if sig["signal"] == "BUY" else orb["high"]
                else:
                    sl = price * 0.995 if sig["signal"] == "BUY" else price * 1.005

                risk_per_share = abs(price - sl)
                if risk_per_share < 0.01:
                    continue

                qty = max(1, int(self.max_loss_per_trade / risk_per_share))
                t1 = price + risk_per_share if sig["signal"] == "BUY" else price - risk_per_share
                t2 = price + 2 * risk_per_share if sig["signal"] == "BUY" else price - 2 * risk_per_share

                current_trade = Trade(
                    date=day_str,
                    symbol=symbol,
                    direction=sig["signal"],
                    entry_time=ts.strftime("%H:%M"),
                    entry_price=price,
                    stop_loss=round(sl, 2),
                    target_1r=round(t1, 2),
                    target_2r=round(t2, 2),
                    qty=qty,
                    confidence=sig["confidence"],
                    strategies=sig["strategies"],
                )
                in_trade = True
                trade_count += 1

        # Force close any open trade at EOD
        if in_trade and current_trade and candles:
            last_ts, last_candle = candles[-1]
            current_trade.exit_price = float(last_candle["close"])
            current_trade.exit_time = last_ts.strftime("%H:%M")
            current_trade.exit_reason = "EOD_EXIT"
            if current_trade.direction == "BUY":
                current_trade.pnl = (current_trade.exit_price - current_trade.entry_price) * current_trade.qty
            else:
                current_trade.pnl = (current_trade.entry_price - current_trade.exit_price) * current_trade.qty
            trades.append(current_trade)

        return trades


def time_obj(h, m):
    from datetime import time as dtime
    return dtime(h, m)