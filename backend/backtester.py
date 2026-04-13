"""
Backtester v2 — Intraday Signal Engine
═══════════════════════════════════════
Rules applied on top of the 7-layer signal engine:

  A. Time Window
     • Entries ONLY between 09:30 and 10:30  (prime money-making window)
     • NO new entries after 13:45            (no-trade zone)
     • EOD hard exit at 15:15

  B. VWAP + 9 EMA Dynamic Exit
     • For a live SELL trade: if price crosses BACK above VWAP or EMA9
       → exit immediately (VWAP_EXIT), don't wait for SL
     • For a live BUY trade: if price crosses BACK below VWAP and EMA9
       → exit immediately (VWAP_EXIT)

  C. SL capped at 1.5% of entry price
     (prevents absurdly wide ORB stops like the ₹8.27 gap on Apr 13)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time as dtime
import pytz
from dataclasses import dataclass, field
from typing import Optional

IST = pytz.timezone("Asia/Kolkata")

from signal_engine import calculate_vwap, calculate_ema, calculate_rsi

# ── Entry / exit time gates ───────────────────
ENTRY_START   = dtime(9, 30)    # earliest entry
ENTRY_CUTOFF  = dtime(10, 30)   # last allowed new entry
NO_TRADE_ZONE = dtime(13, 45)   # no entries after this
EOD_EXIT_TIME = dtime(15, 15)   # hard close all positions


# ═══════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════

@dataclass
class Trade:
    date: str
    symbol: str
    direction: str
    entry_time: str
    entry_price: float
    stop_loss: float
    target_1r: float
    target_2r: float
    exit_price: float = 0.0
    exit_time: str    = ""
    exit_reason: str  = ""   # SL_HIT / T1_HIT / T2_HIT / VWAP_EXIT / EOD_EXIT
    pnl: float        = 0.0
    qty: int          = 1
    confidence: int   = 0
    strategies: dict  = field(default_factory=dict)


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
    def wins(self):  return [t for t in self.trades if t.pnl > 0]

    @property
    def losses(self): return [t for t in self.trades if t.pnl <= 0]

    @property
    def win_rate(self):
        return (len(self.wins) / self.total_trades * 100) if self.total_trades else 0

    @property
    def total_pnl(self): return sum(t.pnl for t in self.trades)

    @property
    def max_drawdown(self):
        if not self.trades: return 0
        peak, max_dd, running = 0, 0, 0
        for t in self.trades:
            running += t.pnl
            if running > peak: peak = running
            dd = peak - running
            if dd > max_dd: max_dd = dd
        return max_dd

    @property
    def profit_factor(self):
        gp = sum(t.pnl for t in self.wins)
        gl = abs(sum(t.pnl for t in self.losses))
        return round(gp / gl, 2) if gl > 0 else float("inf")

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
            if t.pnl <= 0: streak += 1; max_streak = max(max_streak, streak)
            else: streak = 0
        return max_streak

    @property
    def skipped_no_trade_zone(self): return 0   # tracked separately in sim


# ═══════════════════════════════════════════════
# SIGNAL GENERATION (candle-by-candle)
# ═══════════════════════════════════════════════

def get_orb_from_slice(df: pd.DataFrame):
    orb = df.between_time("09:15", "09:29")
    if orb.empty: return None
    return {"high": float(orb["high"].max()), "low": float(orb["low"].min())}


def generate_signal_at_candle(df_upto: pd.DataFrame) -> dict:
    if len(df_upto) < 20:
        return {"signal": "WAIT", "confidence": 0, "strategies": {},
                "price": 0, "vwap": 0, "ema9": 0, "rsi": 0, "orb": None}

    df = df_upto.copy()
    df["vwap"] = calculate_vwap(df)
    df["ema9"] = calculate_ema(df["close"], 9)
    df["rsi"]  = calculate_rsi(df["close"], 14)

    latest   = df.iloc[-1]
    prev     = df.iloc[-2]
    price    = float(latest["close"])
    vwap     = float(latest["vwap"])
    ema9     = float(latest["ema9"])
    rsi      = float(latest["rsi"])
    prev_rsi = float(prev["rsi"])

    bull = bear = 0
    strats = {}

    if price > vwap and ema9 > vwap:
        strats["VWAP"] = "BUY";  bull += 1
    elif price < vwap and ema9 < vwap:
        strats["VWAP"] = "SELL"; bear += 1
    else:
        strats["VWAP"] = "NEUTRAL"

    if float(prev["rsi"]) < 30 and rsi > prev_rsi:
        strats["RSI"] = "BUY";   bull += 1
    elif float(prev["rsi"]) > 70 and rsi < prev_rsi:
        strats["RSI"] = "SELL";  bear += 1
    else:
        strats["RSI"] = "NEUTRAL"

    orb = get_orb_from_slice(df)
    if orb:
        if price > orb["high"]:
            strats["ORB"] = "BUY";  bull += 1
        elif price < orb["low"]:
            strats["ORB"] = "SELL"; bear += 1
        else:
            strats["ORB"] = "IN_RANGE"
    else:
        strats["ORB"] = "NOT_FORMED"

    confidence = max(bull, bear)
    signal = "BUY" if bull >= 2 else ("SELL" if bear >= 2 else "WAIT")

    return {"signal": signal, "confidence": confidence, "strategies": strats,
            "price": price, "vwap": vwap, "ema9": ema9, "rsi": rsi, "orb": orb}


# ═══════════════════════════════════════════════
# CORE BACKTESTER
# ═══════════════════════════════════════════════

class Backtester:
    def __init__(self, capital: float = 5000.0, max_trades_per_day: int = 2,
                 max_sl_pct: float = 0.015):
        """
        capital          : trading capital
        max_trades_per_day: max entries per day
        max_sl_pct       : SL capped at this % of entry price (Rule C — default 1.5%)
        """
        self.capital           = capital
        self.max_trades_per_day = max_trades_per_day
        self.max_loss_per_trade = capital * 0.01
        self.max_sl_pct        = max_sl_pct

    def run(self, df: pd.DataFrame, symbol: str) -> BacktestResult:
        df = df.copy()
        if not hasattr(df.index, "date"):
            df.index = pd.to_datetime(df.index)
        if df.index.tzinfo is None:
            df.index = df.index.tz_localize(IST)
        else:
            df.index = df.index.tz_convert(IST)

        trading_days = sorted(set(df.index.date))
        all_trades   = []

        for day in trading_days:
            day_df = df[df.index.date == day].between_time("09:15", "15:30")
            if len(day_df) < 20:
                continue
            all_trades.extend(self._simulate_day(day_df, symbol, str(day)))

        return BacktestResult(
            symbol=symbol,
            start_date=str(trading_days[0]) if trading_days else "—",
            end_date=str(trading_days[-1])   if trading_days else "—",
            total_days=len(trading_days),
            trades=all_trades,
            capital=self.capital,
        )

    def _simulate_day(self, day_df: pd.DataFrame, symbol: str, day_str: str) -> list:
        trades      = []
        in_trade    = False
        trade_count = 0
        current_trade: Optional[Trade] = None
        candles = list(day_df.iterrows())

        # Cooldown after VWAP_EXIT — block same-direction re-entry for N candles
        COOLDOWN_CANDLES   = 10       # ~10 minutes on 1-min data
        cooldown_until_idx = -1       # candle index until which re-entry is blocked
        cooldown_direction = None     # which direction is cooling down

        for i, (ts, candle) in enumerate(candles):
            t_time = ts.time()
            hi     = float(candle["high"])
            lo     = float(candle["low"])
            close  = float(candle["close"])

            # ── Manage open trade ─────────────────────────────────
            if in_trade and current_trade:
                t = current_trade

                # Compute live VWAP + EMA9 for dynamic exit (Rule B)
                df_now = day_df.iloc[: i + 1].copy()
                df_now["vwap"] = calculate_vwap(df_now)
                df_now["ema9"] = calculate_ema(df_now["close"], 9)
                live_vwap = float(df_now["vwap"].iloc[-1])
                live_ema9 = float(df_now["ema9"].iloc[-1])

                hit = None

                # ── Rule B: VWAP+EMA9 dynamic exit ───────────────
                if t.direction == "SELL":
                    # Exit SELL if price pops back above VWAP OR EMA9
                    if close > live_vwap or close > live_ema9:
                        hit = ("VWAP_EXIT", close)
                elif t.direction == "BUY":
                    # Exit BUY if price falls back below BOTH VWAP and EMA9
                    if close < live_vwap and close < live_ema9:
                        hit = ("VWAP_EXIT", close)

                # ── Standard SL / Target checks ───────────────────
                if not hit:
                    if t.direction == "BUY":
                        if lo <= t.stop_loss:        hit = ("SL_HIT",  t.stop_loss)
                        elif hi >= t.target_2r:      hit = ("T2_HIT",  t.target_2r)
                        elif hi >= t.target_1r:      hit = ("T1_HIT",  t.target_1r)
                    else:
                        if hi >= t.stop_loss:        hit = ("SL_HIT",  t.stop_loss)
                        elif lo <= t.target_2r:      hit = ("T2_HIT",  t.target_2r)
                        elif lo <= t.target_1r:      hit = ("T1_HIT",  t.target_1r)

                # ── EOD hard exit ─────────────────────────────────
                if not hit and t_time >= EOD_EXIT_TIME:
                    hit = ("EOD_EXIT", close)

                if hit:
                    reason, exit_px = hit
                    t.exit_price  = exit_px
                    t.exit_time   = ts.strftime("%H:%M")
                    t.exit_reason = reason
                    t.pnl = (exit_px - t.entry_price) * t.qty if t.direction == "BUY" \
                       else (t.entry_price - exit_px) * t.qty
                    trades.append(t)
                    # If VWAP_EXIT, cool down re-entry in same direction
                    if reason == "VWAP_EXIT":
                        cooldown_until_idx = i + COOLDOWN_CANDLES
                        cooldown_direction = t.direction
                    in_trade = False
                    current_trade = None
                continue

            # ── Gate: no new entries if already in trade or limit hit ──
            if in_trade or trade_count >= self.max_trades_per_day:
                continue

            # ── Rule A: Time window gate ──────────────────────────
            if t_time < ENTRY_START:
                continue                          # too early (ORB not confirmed)
            if t_time > ENTRY_CUTOFF:
                continue                          # outside prime window 9:30–10:30

            # ── Cooldown gate (post VWAP_EXIT) ────────────────────
            # Generate signal first to know direction before blocking
            df_upto_peek = day_df.iloc[: i + 1]
            peek_sig = generate_signal_at_candle(df_upto_peek)
            if (i <= cooldown_until_idx and
                    cooldown_direction is not None and
                    peek_sig["signal"] == cooldown_direction):
                continue                          # same direction still cooling down
            # Note: NO_TRADE_ZONE (13:45) is a secondary guard for any future
            # strategies that widen the entry window

            # ── Generate signal (reuse peek from cooldown check) ──
            sig = peek_sig

            if sig["signal"] not in ("BUY", "SELL"):
                continue

            price = float(candle["close"])
            orb   = sig.get("orb")

            # ── Determine SL ─────────────────────────────────────
            if orb:
                raw_sl = orb["low"] if sig["signal"] == "BUY" else orb["high"]
            else:
                raw_sl = price * (1 - 0.005) if sig["signal"] == "BUY" else price * (1 + 0.005)

            # ── Rule C: Cap SL at max_sl_pct of entry price ──────
            max_sl_distance = price * self.max_sl_pct
            if sig["signal"] == "BUY":
                sl = max(raw_sl, price - max_sl_distance)   # don't put SL too far below
            else:
                sl = min(raw_sl, price + max_sl_distance)   # don't put SL too far above

            risk_per_share = abs(price - sl)
            if risk_per_share < 0.01:
                continue

            qty = max(1, int(self.max_loss_per_trade / risk_per_share))
            t1  = price + risk_per_share if sig["signal"] == "BUY" else price - risk_per_share
            t2  = price + 2 * risk_per_share if sig["signal"] == "BUY" else price - 2 * risk_per_share

            current_trade = Trade(
                date=day_str, symbol=symbol,
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
            in_trade    = True
            trade_count += 1

        # ── Force-close any open trade at EOD ────────────────────
        if in_trade and current_trade and candles:
            last_ts, last_candle = candles[-1]
            current_trade.exit_price  = float(last_candle["close"])
            current_trade.exit_time   = last_ts.strftime("%H:%M")
            current_trade.exit_reason = "EOD_EXIT"
            current_trade.pnl = (
                (current_trade.exit_price - current_trade.entry_price) * current_trade.qty
                if current_trade.direction == "BUY"
                else (current_trade.entry_price - current_trade.exit_price) * current_trade.qty
            )
            trades.append(current_trade)

        return trades