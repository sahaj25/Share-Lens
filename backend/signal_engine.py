"""
Intraday Signal Engine v2 — 7-Layer Confirmation System
────────────────────────────────────────────────────────
Core strategies  : ORB, VWAP, RSI
Advanced filters : Volume Spike, Supertrend, MACD, Nifty Trend (MTF)

Signal fires BUY/SELL only when:
  ① ≥ 2/3 core strategies agree
  ② Volume spike present on breakout candle
  ③ Supertrend (7,3) agrees with direction
  ④ MACD (12,26,9) agrees with direction
  ⑤ Nifty trend aligns (soft block — downgrades to WEAK if against)
"""

import pandas as pd
import numpy as np
from datetime import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")


# ═══════════════════════════════════════════════════════
# INDICATOR CALCULATIONS
# ═══════════════════════════════════════════════════════

def calculate_vwap(df: pd.DataFrame) -> pd.Series:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    return (tp * df["volume"]).cumsum() / df["volume"].cumsum()


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def calculate_supertrend(df: pd.DataFrame, period: int = 7, multiplier: float = 3.0) -> pd.Series:
    """Supertrend (7,3). Returns Series of 'BUY' or 'SELL' per candle."""
    hl2 = (df["high"] + df["low"]) / 2
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"]  - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(span=period, adjust=False).mean()

    basic_upper = hl2 + multiplier * atr
    basic_lower = hl2 - multiplier * atr

    upper = basic_upper.copy()
    lower = basic_lower.copy()
    direction = pd.Series("BUY", index=df.index)

    for i in range(1, len(df)):
        upper.iloc[i] = basic_upper.iloc[i] if (basic_upper.iloc[i] < upper.iloc[i-1] or
                         df["close"].iloc[i-1] > upper.iloc[i-1]) else upper.iloc[i-1]
        lower.iloc[i] = basic_lower.iloc[i] if (basic_lower.iloc[i] > lower.iloc[i-1] or
                         df["close"].iloc[i-1] < lower.iloc[i-1]) else lower.iloc[i-1]

        if direction.iloc[i-1] == "SELL" and df["close"].iloc[i] > upper.iloc[i-1]:
            direction.iloc[i] = "BUY"
        elif direction.iloc[i-1] == "BUY" and df["close"].iloc[i] < lower.iloc[i-1]:
            direction.iloc[i] = "SELL"
        else:
            direction.iloc[i] = direction.iloc[i-1]

    return direction


def calculate_macd(series: pd.Series, fast=12, slow=26, signal=9):
    """Returns (macd_line, signal_line, histogram)"""
    ema_fast   = series.ewm(span=fast,   adjust=False).mean()
    ema_slow   = series.ewm(span=slow,   adjust=False).mean()
    macd_line  = ema_fast - ema_slow
    signal_line= macd_line.ewm(span=signal, adjust=False).mean()
    histogram  = macd_line - signal_line
    return macd_line, signal_line, histogram


def calculate_volume_spike(df: pd.DataFrame, lookback: int = 10) -> pd.Series:
    """True if current candle volume > average of previous `lookback` candles."""
    avg_vol = df["volume"].shift(1).rolling(lookback).mean()
    return df["volume"] > avg_vol


def get_orb_levels(df: pd.DataFrame) -> dict | None:
    if df is None or df.empty:
        return None
    if not pd.api.types.is_datetime64_any_dtype(df.index):
        return None
    orb_candles = df.between_time("09:15", "09:29")
    if orb_candles.empty:
        return None
    now_ist = datetime.now(IST)
    orb_end = now_ist.replace(hour=9, minute=30, second=0, microsecond=0)
    return {
        "high":   float(orb_candles["high"].max()),
        "low":    float(orb_candles["low"].min()),
        "formed": now_ist >= orb_end,
    }


# ═══════════════════════════════════════════════════════
# NIFTY TREND  (Multi-Timeframe context)
# ═══════════════════════════════════════════════════════

def get_nifty_trend(nifty_df: pd.DataFrame | None) -> str:
    """
    Returns 'BULLISH', 'BEARISH', or 'NEUTRAL'.
    Uses today's opening price + 60-period EMA as reference.
    """
    if nifty_df is None or nifty_df.empty:
        return "UNKNOWN"
    try:
        opening = float(nifty_df.iloc[0]["open"])
        current = float(nifty_df.iloc[-1]["close"])
        ema60   = float(calculate_ema(nifty_df["close"], 60).iloc[-1])
        if current > opening and current > ema60:
            return "BULLISH"
        elif current < opening and current < ema60:
            return "BEARISH"
        else:
            return "NEUTRAL"
    except Exception:
        return "UNKNOWN"


# ═══════════════════════════════════════════════════════
# MAIN ANALYSIS — 7-LAYER ENGINE
# ═══════════════════════════════════════════════════════

def analyse_symbol(df: pd.DataFrame, symbol: str,
                   capital: float = 5000,
                   nifty_df: pd.DataFrame | None = None) -> dict:
    """
    Runs all 7 confirmation layers and returns a signal dict.
    nifty_df: today's 1-min Nifty candles (optional but recommended).
    """
    result = {
        "symbol":       symbol,
        "timestamp":    datetime.now(IST).strftime("%H:%M:%S"),
        "price":        None,
        "signal":       "WAIT",
        "confidence":   0,        # core votes 0-3
        "filter_score": 0,        # advanced filters passed 0-3
        "strategies":   {},
        "filters":      {},
        "blocked_by":   [],
        "risk":         {},
        "orb":          None,
        "vwap":         None,
        "rsi":          None,
        "ema9":         None,
        "macd":         None,
        "supertrend":   None,
        "volume_spike": False,
        "nifty_trend":  "UNKNOWN",
    }

    if df is None or len(df) < 30:
        result["error"] = "Insufficient data (need ≥ 30 candles)"
        return result

    df = df.copy()

    # ── Compute all indicators ─────────────────────────────
    df["vwap"]       = calculate_vwap(df)
    df["ema9"]       = calculate_ema(df["close"], 9)
    df["rsi"]        = calculate_rsi(df["close"], 14)
    df["supertrend"] = calculate_supertrend(df, period=7, multiplier=3.0)
    df["vol_spike"]  = calculate_volume_spike(df, lookback=10)
    macd_l, macd_s, macd_h = calculate_macd(df["close"])
    df["macd"]       = macd_l
    df["macd_sig"]   = macd_s

    latest   = df.iloc[-1]
    prev     = df.iloc[-2]

    price     = float(latest["close"])
    vwap      = float(latest["vwap"])
    ema9      = float(latest["ema9"])
    rsi       = float(latest["rsi"])
    prev_rsi  = float(prev["rsi"])
    st_dir    = str(latest["supertrend"])
    vol_spike = bool(latest["vol_spike"])
    macd_val  = float(latest["macd"])
    macd_sig  = float(latest["macd_sig"])
    prev_macd = float(prev["macd"])
    prev_msig = float(prev["macd_sig"])

    result.update({
        "price":       price,
        "vwap":        round(vwap, 2),
        "rsi":         round(rsi, 2),
        "ema9":        round(ema9, 2),
        "supertrend":  st_dir,
        "volume_spike":vol_spike,
        "macd":        round(macd_val, 4),
    })

    # ═══════════════════════════════════════
    # LAYERS 1-3 : CORE STRATEGIES
    # ═══════════════════════════════════════
    bull = bear = 0
    strats = {}

    # 1 — VWAP
    if price > vwap and ema9 > vwap:
        strats["VWAP"] = "BUY";  bull += 1
    elif price < vwap and ema9 < vwap:
        strats["VWAP"] = "SELL"; bear += 1
    else:
        strats["VWAP"] = "NEUTRAL"

    # 2 — RSI Reversal
    if prev_rsi < 30 and rsi > prev_rsi:
        strats["RSI"] = "BUY";   bull += 1
    elif prev_rsi > 70 and rsi < prev_rsi:
        strats["RSI"] = "SELL";  bear += 1
    else:
        strats["RSI"] = "NEUTRAL"

    # 3 — ORB
    orb = get_orb_levels(df)
    result["orb"] = orb
    if orb and orb["formed"]:
        if price > orb["high"]:
            strats["ORB"] = "BUY";  bull += 1
        elif price < orb["low"]:
            strats["ORB"] = "SELL"; bear += 1
        else:
            strats["ORB"] = "IN_RANGE"
    else:
        strats["ORB"] = "NOT_FORMED"

    result["strategies"] = strats
    result["confidence"]  = max(bull, bear)

    core_signal = "BUY" if bull >= 2 else ("SELL" if bear >= 2 else "WAIT")

    if core_signal == "WAIT":
        result["signal"]  = "WAIT"
        result["filters"] = {k: "SKIP" for k in ["VOLUME", "SUPERTREND", "MACD", "NIFTY"]}
        _add_risk(result, price, vwap, orb, capital)
        return result

    # ═══════════════════════════════════════
    # LAYERS 4-7 : ADVANCED FILTERS
    # ═══════════════════════════════════════
    filters    = {}
    blocked_by = []
    fscore     = 0

    # 4 — Volume Spike
    if vol_spike:
        filters["VOLUME"] = "✓ SPIKE"; fscore += 1
    else:
        filters["VOLUME"] = "✗ WEAK";  blocked_by.append("VOLUME")

    # 5 — Supertrend
    if (core_signal == "BUY"  and st_dir == "BUY") or \
       (core_signal == "SELL" and st_dir == "SELL"):
        filters["SUPERTREND"] = f"✓ {'GREEN' if core_signal=='BUY' else 'RED'}"; fscore += 1
    else:
        filters["SUPERTREND"] = f"✗ {st_dir}"; blocked_by.append("SUPERTREND")

    # 6 — MACD
    macd_cross_up   = (prev_macd <= prev_msig) and (macd_val > macd_sig)
    macd_cross_down = (prev_macd >= prev_msig) and (macd_val < macd_sig)

    if core_signal == "BUY":
        if macd_val > macd_sig:
            filters["MACD"] = "✓ CROSS↑" if macd_cross_up else "✓ ABOVE"; fscore += 1
        else:
            filters["MACD"] = "✗ BEARISH"; blocked_by.append("MACD")
    else:
        if macd_val < macd_sig:
            filters["MACD"] = "✓ CROSS↓" if macd_cross_down else "✓ BELOW"; fscore += 1
        else:
            filters["MACD"] = "✗ BULLISH"; blocked_by.append("MACD")

    # 7 — Nifty Trend (soft block)
    nifty_trend = get_nifty_trend(nifty_df)
    result["nifty_trend"] = nifty_trend
    nifty_blocked = False

    if nifty_trend == "UNKNOWN":
        filters["NIFTY"] = "? NO DATA"
    elif core_signal == "BUY"  and nifty_trend == "BULLISH":
        filters["NIFTY"] = "✓ BULLISH"; fscore += 1
    elif core_signal == "SELL" and nifty_trend == "BEARISH":
        filters["NIFTY"] = "✓ BEARISH"; fscore += 1
    else:
        filters["NIFTY"] = f"✗ {nifty_trend}"
        nifty_blocked = True
        blocked_by.append("NIFTY")

    result["filters"]      = filters
    result["filter_score"] = fscore
    result["blocked_by"]   = blocked_by

    # ═══════════════════════════════════════
    # FINAL GATE
    # Hard blocks  : VOLUME, SUPERTREND, MACD → any failure = WAIT
    # Soft block   : NIFTY against → downgrades to WEAK signal (trade with caution)
    # ═══════════════════════════════════════
    hard_blocked = [b for b in blocked_by if b != "NIFTY"]

    if not hard_blocked and not nifty_blocked:
        result["signal"] = core_signal           # 🟢 Full signal
    elif not hard_blocked and nifty_blocked:
        result["signal"] = f"WEAK_{core_signal}" # 🟡 Nifty against — reduced conviction
    else:
        result["signal"] = "WAIT"                # 🔴 Hard filter failed

    _add_risk(result, price, vwap, orb, capital)
    return result


# ═══════════════════════════════════════════════════════
# RISK MANAGEMENT
# ═══════════════════════════════════════════════════════

def _add_risk(result: dict, price: float, vwap: float,
              orb: dict | None, capital: float):
    sig     = result["signal"]
    max_loss = capital * 0.01

    if orb and orb.get("formed"):
        if "BUY" in sig:
            sl = orb["low"];  risk_ps = max(price - sl, 0.01)
        elif "SELL" in sig:
            sl = orb["high"]; risk_ps = max(sl - price, 0.01)
        else:
            sl = vwap;        risk_ps = max(abs(price - vwap), price * 0.005)
    else:
        sl      = vwap
        risk_ps = max(abs(price - vwap), price * 0.005)

    qty = max(1, int(max_loss / risk_ps))

    result["risk"] = {
        "max_loss_per_trade": round(max_loss, 2),
        "stop_loss_price":    round(sl, 2),
        "risk_per_share":     round(risk_ps, 2),
        "suggested_qty":      qty,
        "target_1R": round(price + max_loss / qty, 2) if "BUY"  in sig
                else round(price - max_loss / qty, 2),
        "target_2R": round(price + 2 * max_loss / qty, 2) if "BUY"  in sig
                else round(price - 2 * max_loss / qty, 2),
    }