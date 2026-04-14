"""
Backtester v3 — Full 7-Layer Strategy Backtest
═══════════════════════════════════════════════
Now calls analyse_symbol() from signal_engine.py directly —
the EXACT same logic as the live dashboard:

  Core    : ORB + VWAP + RSI  (≥2/3 must agree)
  Filters : Volume Spike + Supertrend(7,3) + MACD(12,26,9)  [all 3 must pass]
  Context : Nifty trend alignment  (soft block → WEAK signal)

Additional backtest-specific rules:
  A. Time Window   : entries only 09:30–10:30
  B. VWAP+EMA9 exit: dynamic exit if price crosses back through VWAP/EMA9
  C. SL cap 1.5%  : already inside signal_engine._add_risk
  D. Cooldown      : 10-candle block after VWAP_EXIT in same direction
  E. WEAK signals  : treated as valid entries (Nifty data limited in backtest)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time as dtime
import pytz
from dataclasses import dataclass, field
from typing import Optional

IST = pytz.timezone("Asia/Kolkata")

# ── Import the FULL live signal engine ───────────────
from signal_engine import (
    analyse_symbol,
    calculate_vwap,
    calculate_ema,
)

# ── Time gates ────────────────────────────────────────
ENTRY_START   = dtime(9, 30)
ENTRY_CUTOFF  = dtime(10, 30)
EOD_EXIT_TIME = dtime(15, 15)
COOLDOWN_CANDLES = 10          # candles to wait after VWAP_EXIT


# ═══════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════

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
    exit_price: float  = 0.0
    exit_time: str     = ""
    exit_reason: str   = ""
    pnl: float         = 0.0
    qty: int           = 1
    confidence: int    = 0       # core strategy votes
    filter_score: int  = 0       # advanced filters passed
    signal_type: str   = ""      # BUY / SELL / WEAK_BUY / WEAK_SELL
    filters: dict      = field(default_factory=dict)
    strategies: dict   = field(default_factory=dict)
    blocked_by: list   = field(default_factory=list)


@dataclass
class BacktestResult:
    symbol: str
    start_date: str
    end_date: str
    total_days: int
    trades: list
    capital: float
    signals_blocked: int = 0     # how many times full 7-layer filter blocked a trade
    trend_scores: dict   = None  # per-day trendiness score dicts

    def __post_init__(self):
        if self.trend_scores is None:
            self.trend_scores = {}

    @property
    def days_skipped_by_trend(self):
        return sum(1 for v in self.trend_scores.values() if not v["pass"])

    @property
    def days_traded_by_trend(self):
        return sum(1 for v in self.trend_scores.values() if v["pass"])

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
        peak = max_dd = running = 0
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



# ═══════════════════════════════════════════════════════
# PRE-MARKET TRENDINESS FILTER
# ═══════════════════════════════════════════════════════

def score_trendiness(df: pd.DataFrame, lookback_days: int = 3) -> dict:
    """
    Scores a stock's trendiness using the past `lookback_days` of daily closes.
    Returns a score dict with a pass/fail recommendation.

    Checks:
      1. Net move    : abs(close[-1] - close[0]) / close[0]  ≥ 2%
      2. Consistency : ≥ 60% of days moved in the same direction
      3. ATR ratio   : avg daily range / avg close ≥ 0.8%  (not too flat)
      4. Volume trend: avg volume last 3 days vs prior 3 days  ≥ 1.0x

    Score 0-4 (one point per check). Pass threshold = 2.
    """
    if df is None or df.empty:
        return {"score": 0, "pass": False, "reason": "No data", "details": {}}

    # Build daily OHLCV from 1-min data
    daily = df.resample("D").agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    ).dropna()

    if len(daily) < 2:
        return {"score": 0, "pass": False, "reason": "Insufficient daily bars", "details": {}}

    recent = daily.tail(lookback_days)
    closes = recent["close"].values
    volumes = recent["volume"].values

    score = 0
    details = {}

    # 1 — Net move ≥ 2%
    net_move_pct = abs(closes[-1] - closes[0]) / closes[0] * 100
    details["net_move_pct"] = round(net_move_pct, 2)
    if net_move_pct >= 2.0:
        score += 1
        details["net_move"] = "✓ TRENDING"
    else:
        details["net_move"] = f"✗ FLAT ({net_move_pct:.1f}%)"

    # 2 — Directional consistency ≥ 60% of days same direction
    if len(closes) >= 2:
        daily_moves = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        up_days = sum(1 for m in daily_moves if m > 0)
        down_days = sum(1 for m in daily_moves if m < 0)
        dominant = max(up_days, down_days)
        consistency = dominant / len(daily_moves) if daily_moves else 0
        direction = "UP" if up_days >= down_days else "DOWN"
        details["direction"] = direction
        details["consistency_pct"] = round(consistency * 100, 1)
        if consistency >= 0.6:
            score += 1
            details["consistency"] = f"✓ {direction} {consistency*100:.0f}%"
        else:
            details["consistency"] = f"✗ CHOPPY ({consistency*100:.0f}%)"
    else:
        details["consistency"] = "✗ INSUFFICIENT DATA"

    # 3 — ATR ratio (volatility check — not too flat)
    daily_ranges = (recent["high"] - recent["low"]).values
    avg_range = daily_ranges.mean()
    avg_close = closes.mean()
    atr_ratio = avg_range / avg_close * 100
    details["atr_ratio_pct"] = round(atr_ratio, 2)
    if atr_ratio >= 0.8:
        score += 1
        details["volatility"] = f"✓ ACTIVE ({atr_ratio:.1f}%)"
    else:
        details["volatility"] = f"✗ FLAT ({atr_ratio:.1f}%)"

    # 4 — Volume trend (recent vs prior)
    if len(daily) >= 4:
        prior_vol = daily["volume"].iloc[-6:-3].mean() if len(daily) >= 6 else daily["volume"].iloc[:-3].mean()
        recent_vol = volumes.mean()
        vol_ratio = recent_vol / prior_vol if prior_vol > 0 else 1.0
        details["volume_ratio"] = round(vol_ratio, 2)
        if vol_ratio >= 1.0:
            score += 1
            details["volume_trend"] = f"✓ RISING ({vol_ratio:.1f}x)"
        else:
            details["volume_trend"] = f"✗ FALLING ({vol_ratio:.1f}x)"
    else:
        score += 1   # give benefit of doubt if not enough history
        details["volume_trend"] = "? INSUFFICIENT HISTORY"

    passed = score >= 2
    reason = f"Score {score}/4 — {'TRADEABLE' if passed else 'SKIP — not trending'}"

    return {
        "score":     score,
        "pass":      passed,
        "reason":    reason,
        "direction": details.get("direction", "UNKNOWN"),
        "details":   details,
    }


# ═══════════════════════════════════════════════════════
# CORE BACKTESTER
# ═══════════════════════════════════════════════════════

class Backtester:
    def __init__(self, capital: float = 5000.0, max_trades_per_day: int = 2,
                 trend_filter: bool = True, trend_min_score: int = 2,
                 trend_lookback_days: int = 3):
        """
        trend_filter       : if True, skip symbols that don't pass trendiness check
        trend_min_score    : minimum trendiness score (0-4) to allow trading
        trend_lookback_days: how many past days to score trendiness on
        """
        self.capital             = capital
        self.max_trades_per_day  = max_trades_per_day
        self.max_loss_per_trade  = capital * 0.01
        self.trend_filter        = trend_filter
        self.trend_min_score     = trend_min_score
        self.trend_lookback_days = trend_lookback_days

    def run(self, df: pd.DataFrame, symbol: str,
            nifty_df: pd.DataFrame | None = None) -> BacktestResult:
        """
        df       : full historical 1-min OHLCV for the symbol
        nifty_df : full historical 1-min OHLCV for Nifty (optional, for MTF filter)
        """
        df = self._ensure_tz(df)
        if nifty_df is not None:
            nifty_df = self._ensure_tz(nifty_df)

        trading_days    = sorted(set(df.index.date))
        all_trades      = []
        total_blocked   = 0

        trend_scores = {}   # date_str -> trendiness dict

        for day in trading_days:
            day_df = df[df.index.date == day].between_time("09:15", "15:30")
            if len(day_df) < 30:
                continue

            # ── Trendiness filter: score using data BEFORE today ──────
            if self.trend_filter:
                history_df = df[df.index.date < day]
                ts = score_trendiness(history_df, self.trend_lookback_days)
                trend_scores[str(day)] = ts
                if not ts["pass"]:
                    continue   # skip this day entirely — stock not trending

            # Slice nifty to same day
            day_nifty = None
            if nifty_df is not None:
                day_nifty = nifty_df[nifty_df.index.date == day].between_time("09:15", "15:30")
                if day_nifty.empty:
                    day_nifty = None

            trades, blocked = self._simulate_day(day_df, day_nifty, symbol, str(day))
            all_trades.extend(trades)
            total_blocked += blocked

        return BacktestResult(
            symbol=symbol,
            start_date=str(trading_days[0]) if trading_days else "—",
            end_date=str(trading_days[-1])   if trading_days else "—",
            total_days=len(trading_days),
            trades=all_trades,
            capital=self.capital,
            signals_blocked=total_blocked,
            trend_scores=trend_scores if self.trend_filter else {},
        )

    def _simulate_day(self, day_df: pd.DataFrame,
                      day_nifty: pd.DataFrame | None,
                      symbol: str, day_str: str) -> tuple[list, int]:
        trades      = []
        in_trade    = False
        trade_count = 0
        current_trade: Optional[Trade] = None
        candles = list(day_df.iterrows())
        blocked_count = 0

        cooldown_until_idx = -1
        cooldown_direction = None

        for i, (ts, candle) in enumerate(candles):
            t_time = ts.time()
            hi     = float(candle["high"])
            lo     = float(candle["low"])
            close  = float(candle["close"])

            # ════════════════════════════════════
            # MANAGE OPEN TRADE
            # ════════════════════════════════════
            if in_trade and current_trade:
                t = current_trade

                # Live VWAP + EMA9 for dynamic exit
                df_now       = day_df.iloc[: i + 1].copy()
                df_now["vwap"] = calculate_vwap(df_now)
                df_now["ema9"] = calculate_ema(df_now["close"], 9)
                live_vwap    = float(df_now["vwap"].iloc[-1])
                live_ema9    = float(df_now["ema9"].iloc[-1])

                hit = None

                # Rule B — VWAP+EMA9 dynamic exit
                if t.direction in ("BUY", "WEAK_BUY"):
                    if close < live_vwap and close < live_ema9:
                        hit = ("VWAP_EXIT", close)
                elif t.direction in ("SELL", "WEAK_SELL"):
                    if close > live_vwap or close > live_ema9:
                        hit = ("VWAP_EXIT", close)

                # Standard SL / Target
                if not hit:
                    base_dir = "BUY" if "BUY" in t.direction else "SELL"
                    if base_dir == "BUY":
                        if lo <= t.stop_loss:   hit = ("SL_HIT",  t.stop_loss)
                        elif hi >= t.target_2r: hit = ("T2_HIT",  t.target_2r)
                        elif hi >= t.target_1r: hit = ("T1_HIT",  t.target_1r)
                    else:
                        if hi >= t.stop_loss:   hit = ("SL_HIT",  t.stop_loss)
                        elif lo <= t.target_2r: hit = ("T2_HIT",  t.target_2r)
                        elif lo <= t.target_1r: hit = ("T1_HIT",  t.target_1r)

                # EOD exit
                if not hit and t_time >= EOD_EXIT_TIME:
                    hit = ("EOD_EXIT", close)

                if hit:
                    reason, exit_px = hit
                    t.exit_price  = exit_px
                    t.exit_time   = ts.strftime("%H:%M")
                    t.exit_reason = reason
                    base_dir = "BUY" if "BUY" in t.direction else "SELL"
                    t.pnl = (exit_px - t.entry_price) * t.qty if base_dir == "BUY" \
                       else (t.entry_price - exit_px) * t.qty
                    trades.append(t)
                    if reason == "VWAP_EXIT":
                        cooldown_until_idx = i + COOLDOWN_CANDLES
                        cooldown_direction = t.direction
                    in_trade      = False
                    current_trade = None
                continue

            # ════════════════════════════════════
            # LOOK FOR NEW ENTRY
            # ════════════════════════════════════
            if in_trade or trade_count >= self.max_trades_per_day:
                continue

            # Rule A — time window
            if t_time < ENTRY_START or t_time > ENTRY_CUTOFF:
                continue

            # ── Run FULL 7-layer signal engine ────────────────────
            df_upto    = day_df.iloc[: i + 1]

            # Build nifty slice up to this candle's timestamp
            nifty_upto = None
            if day_nifty is not None:
                nifty_upto = day_nifty[day_nifty.index <= ts]
                if nifty_upto.empty:
                    nifty_upto = None

            sig = analyse_symbol(
                df_upto, symbol,
                capital=self.capital,
                nifty_df=nifty_upto
            )

            raw_signal = sig.get("signal", "WAIT")

            # Accept BUY, SELL, WEAK_BUY, WEAK_SELL
            if raw_signal not in ("BUY", "SELL", "WEAK_BUY", "WEAK_SELL"):
                # Core was valid but hard filters blocked — count it
                if sig.get("confidence", 0) >= 2:
                    blocked_count += 1
                continue

            # Cooldown gate
            base_dir = "BUY" if "BUY" in raw_signal else "SELL"
            if (i <= cooldown_until_idx and
                    cooldown_direction is not None and
                    base_dir in cooldown_direction):
                continue

            price = sig.get("price") or float(candle["close"])
            risk  = sig.get("risk", {})
            sl    = risk.get("stop_loss_price", price * 0.985 if base_dir == "BUY" else price * 1.015)
            t1    = risk.get("target_1R", price)
            t2    = risk.get("target_2R", price)
            qty   = risk.get("suggested_qty", 1)

            current_trade = Trade(
                date=day_str,
                symbol=symbol,
                direction=raw_signal,
                entry_time=ts.strftime("%H:%M"),
                entry_price=price,
                stop_loss=sl,
                target_1r=t1,
                target_2r=t2,
                qty=qty,
                confidence=sig.get("confidence", 0),
                filter_score=sig.get("filter_score", 0),
                signal_type=raw_signal,
                filters=sig.get("filters", {}),
                strategies=sig.get("strategies", {}),
                blocked_by=sig.get("blocked_by", []),
            )
            in_trade    = True
            trade_count += 1

        # Force-close at EOD
        if in_trade and current_trade and candles:
            last_ts, last_candle = candles[-1]
            current_trade.exit_price  = float(last_candle["close"])
            current_trade.exit_time   = last_ts.strftime("%H:%M")
            current_trade.exit_reason = "EOD_EXIT"
            base_dir = "BUY" if "BUY" in current_trade.direction else "SELL"
            current_trade.pnl = (
                (current_trade.exit_price - current_trade.entry_price) * current_trade.qty
                if base_dir == "BUY"
                else (current_trade.entry_price - current_trade.exit_price) * current_trade.qty
            )
            trades.append(current_trade)

        return trades, blocked_count

    @staticmethod
    def _ensure_tz(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        if not hasattr(df.index, "date"):
            df.index = pd.to_datetime(df.index)
        if df.index.tzinfo is None:
            df.index = df.index.tz_localize(IST)
        else:
            df.index = df.index.tz_convert(IST)
        return df