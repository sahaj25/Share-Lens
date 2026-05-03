import numpy as np
import pandas as pd


def compute_atr(df, period=14):
    """ATR using RMA (Wilder's smoothing) — matches Pine's ta.atr()"""
    high = df['high']
    low = df['low']
    close = df['close']

    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low  - close.shift(1)).abs()
    ], axis=1).max(axis=1)

    # RMA = EWM with alpha = 1/period, adjust=False
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    return atr


def compute_ema(series, period):
    """EMA matching Pine's ta.ema() — adjust=False"""
    return series.ewm(span=period, adjust=False).mean()


def compute_rsi(series, period=14):
    """
    RSI using Wilder's RMA smoothing — matches Pine's ta.rsi()
    The ta library does this correctly but we implement explicitly
    to guarantee parity.
    """
    delta = series.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)

    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()

    rs  = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def compute_supertrend(df, period=14, multiplier=3):
    """
    Supertrend matching Pine's ta.supertrend().
    stBull (Pine) = direction < 0 = our ST_dir == -1
    """
    high  = df['high'].values
    low   = df['low'].values
    close = df['close'].values
    atr   = compute_atr(df, period).values

    hl2         = (high + low) / 2
    upper_basic = hl2 + multiplier * atr
    lower_basic = hl2 - multiplier * atr

    final_upper = upper_basic.copy()
    final_lower = lower_basic.copy()
    direction   = np.ones(len(df), dtype=int)  # 1=bearish, -1=bullish

    for i in range(1, len(df)):
        # Final upper band
        if upper_basic[i] < final_upper[i-1] or close[i-1] > final_upper[i-1]:
            final_upper[i] = upper_basic[i]
        else:
            final_upper[i] = final_upper[i-1]

        # Final lower band
        if lower_basic[i] > final_lower[i-1] or close[i-1] < final_lower[i-1]:
            final_lower[i] = lower_basic[i]
        else:
            final_lower[i] = final_lower[i-1]

        # Direction (matches Pine logic exactly)
        if direction[i-1] == 1:          # was bearish
            direction[i] = -1 if close[i] > final_upper[i] else 1
        else:                             # was bullish
            direction[i] =  1 if close[i] < final_lower[i] else -1

    df = df.copy()
    df["ST_dir"]         = direction
    df["ST_final_upper"] = final_upper
    df["ST_final_lower"] = final_lower
    return df


def has_signal(df):
    """
    Mirrors Pine's buySignal condition:
        stFlipBull  → ST flipped bullish on the signal bar
        close > EMA20
        40 < RSI < 75

    We check iloc[-2] (yesterday's bar) because:
    - Signal fires when that candle CLOSES
    - We buy on today's open (iloc[-1] bar)
    """
    if len(df) < 50:
        return None

    df = df.copy().reset_index(drop=True)

    # Indicators — all matching Pine
    df["EMA20"] = compute_ema(df["close"], 20)
    df["RSI"]   = compute_rsi(df["close"], 14)
    df          = compute_supertrend(df, period=14, multiplier=3)

    # Signal bar = yesterday = iloc[-2]
    # Previous bar = day before = iloc[-3]
    sig  = df.iloc[-2]   # yesterday — where signal must have fired
    prev = df.iloc[-3]   # day before yesterday

    st_flip_bull = (sig["ST_dir"] == -1) and (prev["ST_dir"] == 1)
    above_ema    = sig["close"] > sig["EMA20"]
    rsi_ok       = 40 < sig["RSI"] < 75

    if st_flip_bull and above_ema and rsi_ok:
        return {
            "price": round(sig["close"], 2),
            "rsi":   round(sig["RSI"], 1),
            "ema20": round(sig["EMA20"], 2),
            "signal_date": sig["time"]   # helpful for verification
        }

    return None