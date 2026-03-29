import os
import pyotp
import time
import numpy as np
from SmartApi import SmartConnect
from datetime import datetime, date
import requests as req
import ntplib


API_KEY    = os.getenv("ANGEL_API_KEY")
CLIENT_ID  = os.getenv("ANGEL_CLIENT_ID")
PASSWORD   = os.getenv("ANGEL_PASSWORD")
TOTP_TOKEN = os.getenv("ANGEL_TOTP_SECRET")

# ── Symbols to track ──────────────────────────────────────────────────────────

WATCHLIST = ["RELIANCE", "TCS", "SBIN"]

SYMBOL_TOKEN_MAP = {
    "RELIANCE": "2885",    "TCS": "11536",      "INFY": "1594",
    "HDFCBANK": "1333",    "ICICIBANK": "4963",  "SBIN": "3045",
    "HINDUNILVR": "1394",  "ITC": "1660",        "KOTAKBANK": "1922",
    "LT": "11483",         "BAJFINANCE": "317",  "AXISBANK": "5900",
    "MARUTI": "10999",     "WIPRO": "3787",      "HCLTECH": "7229",
    "TITAN": "3506",       "NESTLEIND": "17963", "ADANIENT": "25",
    "ULTRACEMCO": "11532", "POWERGRID": "14977",
}

# ── Signal thresholds ─────────────────────────────────────────────────────────

SWING_MIN_SCORE     = 7.0   # out of 10
SWING_MIN_RR        = 2.0   # 1:2 risk/reward minimum
ADX_TREND_THRESHOLD = 25
RSI_OVERSOLD        = 40
RSI_OVERBOUGHT      = 60
VOLUME_SPIKE_RATIO  = 1.5   # intraday volume spike multiplier
INTRADAY_START_H    = 9
INTRADAY_START_M    = 15
INTRADAY_END_H      = 11
INTRADAY_END_M      = 0


# ══════════════════════════════════════════════════════════════════════════════
# NTP CLOCK CORRECTION
# ══════════════════════════════════════════════════════════════════════════════

def get_ntp_offset() -> float:
    try:
        client   = ntplib.NTPClient()
        response = client.request("pool.ntp.org", version=3, timeout=5)
        offset   = response.offset
        print(f"🕐 NTP offset: {offset:+.3f}s")
        return offset
    except Exception as e:
        print(f"⚠️ NTP query failed — using local clock: {e}")
        return 0.0


def get_accurate_time(offset: float) -> float:
    return time.time() + offset


def wait_for_fresh_totp_window(offset: float):
    accurate_now        = get_accurate_time(offset)
    seconds_into_window = accurate_now % 30
    seconds_remaining   = 30 - seconds_into_window

    if seconds_remaining < 5:
        wait = seconds_remaining + 1
        print(f"⏳ Only {seconds_remaining:.1f}s left in TOTP window — waiting {wait:.1f}s...")
        time.sleep(wait)
    else:
        print(f"✅ TOTP window OK ({seconds_remaining:.1f}s remaining)")


def generate_totp_with_ntp(totp_gen: pyotp.TOTP, offset: float) -> str:
    accurate_now = get_accurate_time(offset)
    totp         = totp_gen.at(accurate_now)
    print(f"🔑 TOTP (NTP-corrected, offset {offset:+.3f}s): {totp}")
    return totp


# ══════════════════════════════════════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════════════════════════════════════

def login() -> SmartConnect:
    obj        = SmartConnect(api_key=API_KEY)
    totp_gen   = pyotp.TOTP(TOTP_TOKEN)
    offset     = get_ntp_offset()
    last_error = None

    for attempt in range(5):
        try:
            wait_for_fresh_totp_window(offset)
            utc_now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            totp    = generate_totp_with_ntp(totp_gen, offset)
            print(f"[LOGIN ATTEMPT {attempt + 1}] UTC: {utc_now} | TOTP: {totp}")

            data = obj.generateSession(CLIENT_ID, PASSWORD, totp)
            if data.get("status"):
                print("✅ Login successful")
                return obj

            last_error = data.get("message", "Unknown error")
            print(f"❌ Login failed: {last_error}")

        except Exception as e:
            last_error = str(e)
            print(f"❌ Exception on attempt {attempt + 1}: {e}")

        if attempt < 4:
            print("⏳ Waiting 5s before next attempt...")
            time.sleep(5)

    raise RuntimeError(f"Login failed after 5 attempts: {last_error}")


# ══════════════════════════════════════════════════════════════════════════════
# MARKET DATA
# ══════════════════════════════════════════════════════════════════════════════

def get_token(symbol: str) -> str:
    token = SYMBOL_TOKEN_MAP.get(symbol.upper())
    if token:
        return token

    url    = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
    master = req.get(url, timeout=10).json()
    for item in master:
        if item.get("symbol") == symbol.upper() and item.get("exch_seg") == "NSE":
            return item["token"]

    raise ValueError(f"Token not found for symbol: {symbol}")


def fetch_market_data(obj: SmartConnect, symbol: str) -> dict:
    token = get_token(symbol)
    resp  = obj.getMarketData("FULL", {"NSE": [token]})

    if resp["status"] is False:
        raise RuntimeError(f"getMarketData failed: {resp['message']}")

    fetched = resp["data"].get("fetched", [])
    if not fetched:
        raise RuntimeError(f"No data returned for {symbol}")

    d          = fetched[0]
    ltp        = float(d.get("ltp", 0))
    prev_close = float(d.get("close", 0))
    pct_change = ((ltp - prev_close) / prev_close * 100) if prev_close else 0.0

    return {
        "symbol":      symbol.upper(),
        "ltp":         ltp,
        "open":        float(d.get("open", 0)),
        "high":        float(d.get("high", 0)),
        "low":         float(d.get("low", 0)),
        "prev_close":  prev_close,
        "pct_change":  round(pct_change, 2),
        "volume":      int(d.get("tradeVolume", 0)),
        "week52_high": float(d.get("fiftyTwoWeekHighPrice", 0)),
        "week52_low":  float(d.get("fiftyTwoWeekLowPrice", 0)),
    }


def fetch_candles(obj: SmartConnect, symbol: str, interval: str, days: int) -> list:
    """
    Fetch historical candles via getCandleData.
      interval : "ONE_DAY" for daily candles, "FIVE_MINUTE" for 5-min candles
      days     : how many calendar days back to request
    Returns list of dicts: {timestamp, open, high, low, close, volume}
    """
    token   = get_token(symbol)
    now     = datetime.now()
    from_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Subtract days manually to avoid dateutil dependency
    from_ts = from_dt.replace(day=max(1, from_dt.day - days - 5)).strftime("%Y-%m-%d %H:%M")
    to_ts   = now.strftime("%Y-%m-%d %H:%M")

    params = {
        "exchange":    "NSE",
        "symboltoken": token,
        "interval":    interval,
        "fromdate":    from_ts,
        "todate":      to_ts,
    }

    resp = obj.getCandleData(params)
    if not resp.get("status"):
        raise RuntimeError(f"getCandleData failed for {symbol}: {resp.get('message')}")

    candles = []
    for row in resp.get("data", []):
        # Angel One row format: [timestamp, open, high, low, close, volume]
        candles.append({
            "timestamp": row[0],
            "open":      float(row[1]),
            "high":      float(row[2]),
            "low":       float(row[3]),
            "close":     float(row[4]),
            "volume":    int(row[5]),
        })

    return candles


# ══════════════════════════════════════════════════════════════════════════════
# TECHNICAL INDICATORS
# ══════════════════════════════════════════════════════════════════════════════

def ema(values: list, period: int) -> list:
    """Exponential Moving Average."""
    if not values:
        return []
    result = [values[0]]
    k = 2 / (period + 1)
    for v in values[1:]:
        result.append(v * k + result[-1] * (1 - k))
    return result


def rsi(closes: list, period: int = 14) -> float:
    """RSI of the last candles."""
    if len(closes) < period + 1:
        return 50.0  # neutral fallback

    deltas   = np.diff(closes[-(period + 1):])
    gains    = np.where(deltas > 0, deltas, 0.0)
    losses   = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = np.mean(gains)
    avg_loss = np.mean(losses)

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def adx(candles: list, period: int = 14) -> float:
    """Average Directional Index (ADX)."""
    if len(candles) < period * 2:
        return 0.0

    highs  = [c["high"]  for c in candles]
    lows   = [c["low"]   for c in candles]
    closes = [c["close"] for c in candles]

    tr_list, plus_dm, minus_dm = [], [], []

    for i in range(1, len(candles)):
        h, l, pc = highs[i], lows[i], closes[i - 1]
        tr_list.append(max(h - l, abs(h - pc), abs(l - pc)))
        up   = highs[i]    - highs[i - 1]
        down = lows[i - 1] - lows[i]
        plus_dm.append(up   if up > down and up > 0   else 0)
        minus_dm.append(down if down > up and down > 0 else 0)

    def smooth(arr, p):
        s = [sum(arr[:p])]
        for v in arr[p:]:
            s.append(s[-1] - s[-1] / p + v)
        return s

    str_  = smooth(tr_list,  period)
    spdm  = smooth(plus_dm,  period)
    smdm  = smooth(minus_dm, period)

    di_plus  = [100 * p / t if t else 0 for p, t in zip(spdm, str_)]
    di_minus = [100 * m / t if t else 0 for m, t in zip(smdm, str_)]
    dx = [
        100 * abs(p - m) / (p + m) if (p + m) else 0
        for p, m in zip(di_plus, di_minus)
    ]

    return round(np.mean(dx[-period:]) if len(dx) >= period else 0.0, 2)


def vwap(candles: list) -> float:
    """Volume-Weighted Average Price for the provided candles."""
    cum_pv  = sum(((c["high"] + c["low"] + c["close"]) / 3) * c["volume"] for c in candles)
    cum_vol = sum(c["volume"] for c in candles)
    return round(cum_pv / cum_vol, 2) if cum_vol else 0.0


def support_resistance(candles: list, lookback: int = 20) -> tuple:
    """Simple S/R: lowest low = support, highest high = resistance over lookback."""
    recent  = candles[-lookback:]
    support = min(c["low"]  for c in recent)
    resist  = max(c["high"] for c in recent)
    return round(support, 2), round(resist, 2)


# ══════════════════════════════════════════════════════════════════════════════
# SWING SIGNAL  (daily candles)
# Scoring breakdown (100 pts → /10):
#   EMA 20/50 crossover  : 25 pts
#   ADX > 25             : 20 pts
#   RSI zone             : 20 pts
#   Volume > 20-day avg  : 20 pts
#   S/R proximity        : 15 pts
# Min score: 7/10   Min R/R: 1:2
# ══════════════════════════════════════════════════════════════════════════════

def compute_swing_signal(obj: SmartConnect, symbol: str, ltp: float) -> dict:
    try:
        candles = fetch_candles(obj, symbol, "ONE_DAY", 60)
    except Exception as e:
        return {"error": str(e)}

    if len(candles) < 55:
        return {"error": f"Not enough daily candles (got {len(candles)})"}

    closes  = [c["close"]  for c in candles]
    volumes = [c["volume"] for c in candles]

    # ── Indicators ────────────────────────────────────────────────────────────
    ema20_series = ema(closes, 20)
    ema50_series = ema(closes, 50)
    ema20_now    = ema20_series[-1]
    ema50_now    = ema50_series[-1]
    ema20_prev   = ema20_series[-2]
    ema50_prev   = ema50_series[-2]

    adx_val   = adx(candles, 14)
    rsi_val   = rsi(closes, 14)
    vol_now   = volumes[-1]
    vol_avg20 = np.mean(volumes[-21:-1])   # prior 20-day average (exclude today)

    support, resistance = support_resistance(candles, 20)

    # ── Trend direction ───────────────────────────────────────────────────────
    bullish_cross = ema20_now > ema50_now and ema20_prev <= ema50_prev
    bearish_cross = ema20_now < ema50_now and ema20_prev >= ema50_prev
    trend_up      = ema20_now > ema50_now

    # ── Score (100-pt scale) ──────────────────────────────────────────────────
    score = 0

    # 1. EMA crossover / trend — 25 pts
    if bullish_cross or bearish_cross:
        score += 25           # fresh crossover = full marks
    elif ema20_now != ema50_now:
        score += 15           # established trend

    # 2. ADX strength — 20 pts
    if adx_val >= 35:
        score += 20
    elif adx_val >= ADX_TREND_THRESHOLD:
        score += 12

    # 3. RSI zone — 20 pts
    if trend_up and RSI_OVERSOLD <= rsi_val <= 55:
        score += 20           # bullish entry zone (not overbought)
    elif not trend_up and 45 <= rsi_val <= RSI_OVERBOUGHT:
        score += 20           # bearish entry zone (not oversold)
    elif 40 <= rsi_val <= 65:
        score += 10           # neutral zone, partial credit

    # 4. Volume confirmation — 20 pts
    if vol_avg20 > 0:
        if vol_now >= vol_avg20 * 1.5:
            score += 20
        elif vol_now >= vol_avg20:
            score += 12

    # 5. S/R proximity — 15 pts
    range_sr = resistance - support
    if range_sr > 0:
        pct_from_support = (ltp - support) / range_sr
        if trend_up and pct_from_support <= 0.30:
            score += 15       # near support in uptrend = good long entry
        elif not trend_up and pct_from_support >= 0.70:
            score += 15       # near resistance in downtrend = good short entry
        else:
            score += 5        # partial credit for mid-range

    final_score = round(score / 10, 1)   # 100-pt → /10

    # ── Risk / Reward ─────────────────────────────────────────────────────────
    atr_val = float(np.mean([c["high"] - c["low"] for c in candles[-14:]]))
    if trend_up:
        stop_loss = ltp - atr_val
        target    = ltp + atr_val * SWING_MIN_RR
        direction = "LONG  📈"
    else:
        stop_loss = ltp + atr_val
        target    = ltp - atr_val * SWING_MIN_RR
        direction = "SHORT 📉"

    risk   = abs(ltp - stop_loss)
    reward = abs(target - ltp)
    rr     = round(reward / risk, 2) if risk else 0

    return {
        "score":      final_score,
        "signal":     final_score >= SWING_MIN_SCORE and rr >= SWING_MIN_RR,
        "direction":  direction,
        "ema20":      round(ema20_now, 2),
        "ema50":      round(ema50_now, 2),
        "adx":        adx_val,
        "rsi":        rsi_val,
        "vol_ratio":  round(vol_now / vol_avg20, 2) if vol_avg20 else 0,
        "support":    support,
        "resistance": resistance,
        "stop_loss":  round(stop_loss, 2),
        "target":     round(target, 2),
        "rr":         rr,
    }


# ══════════════════════════════════════════════════════════════════════════════
# INTRADAY SIGNAL  (5-min candles, 9:15–11:00 AM only)
# All 3 conditions must align:
#   1. Price above / below VWAP
#   2. EMA 9 crossover on 5-min candles
#   3. Volume spike ≥ 1.5× average candle volume
# ══════════════════════════════════════════════════════════════════════════════

def is_intraday_window() -> bool:
    now   = datetime.now()
    start = now.replace(hour=INTRADAY_START_H, minute=INTRADAY_START_M, second=0, microsecond=0)
    end   = now.replace(hour=INTRADAY_END_H,   minute=INTRADAY_END_M,   second=0, microsecond=0)
    return start <= now <= end


def compute_intraday_signal(obj: SmartConnect, symbol: str, ltp: float) -> dict:
    if not is_intraday_window():
        return {"active": False, "reason": "Outside intraday window (9:15–11:00 AM IST)"}

    try:
        candles = fetch_candles(obj, symbol, "FIVE_MINUTE", 2)
    except Exception as e:
        return {"active": True, "error": str(e)}

    # Keep only today's candles
    today_str     = date.today().strftime("%Y-%m-%d")
    today_candles = [c for c in candles if str(c["timestamp"]).startswith(today_str)]

    if len(today_candles) < 5:
        return {"active": True, "error": f"Not enough intraday candles yet (got {len(today_candles)})"}

    closes  = [c["close"]  for c in today_candles]
    volumes = [c["volume"] for c in today_candles]

    # 1. VWAP position
    vwap_val   = vwap(today_candles)
    above_vwap = ltp > vwap_val

    # 2. EMA 9 crossover on 5-min
    ema9_series    = ema(closes, 9)
    ema9_now       = ema9_series[-1]
    ema9_prev      = ema9_series[-2] if len(ema9_series) >= 2 else ema9_now
    ema9_cross_up  = closes[-1] > ema9_now  and closes[-2] <= ema9_prev
    ema9_cross_dn  = closes[-1] < ema9_now  and closes[-2] >= ema9_prev

    # 3. Volume spike vs. average of prior candles today
    avg_vol   = float(np.mean(volumes[:-1])) if len(volumes) > 1 else float(volumes[-1])
    vol_ratio = round(volumes[-1] / avg_vol, 2) if avg_vol else 0
    vol_spike = vol_ratio >= VOLUME_SPIKE_RATIO

    # All-3 alignment check
    long_signal  = above_vwap      and ema9_cross_up and vol_spike
    short_signal = (not above_vwap) and ema9_cross_dn  and vol_spike

    if long_signal:
        direction = "LONG  📈"
    elif short_signal:
        direction = "SHORT 📉"
    else:
        direction = "NO SIGNAL"

    # Count how many of the 3 legs are satisfied
    if long_signal or short_signal:
        aligned = 3
    else:
        aligned = sum([
            above_vwap if closes[-1] > vwap_val else not above_vwap,
            ema9_cross_up or ema9_cross_dn,
            vol_spike,
        ])

    return {
        "active":      True,
        "signal":      long_signal or short_signal,
        "direction":   direction,
        "aligned":     f"{aligned}/3",
        "vwap":        vwap_val,
        "above_vwap":  above_vwap,
        "ema9":        round(ema9_now, 2),
        "ema9_cross":  ema9_cross_up or ema9_cross_dn,
        "vol_spike":   vol_spike,
        "vol_ratio":   vol_ratio,
    }


# ══════════════════════════════════════════════════════════════════════════════
# FORMATTING
# ══════════════════════════════════════════════════════════════════════════════

def format_snapshot_message(data: dict) -> str:
    arrow = "🟢" if data["pct_change"] >= 0 else "🔴"
    sign  = "+" if data["pct_change"] >= 0 else ""
    return (
        f"{arrow} *{data['symbol']}*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"💰 LTP       : ₹{data['ltp']:.2f}\n"
        f"📈 Open      : ₹{data['open']:.2f}\n"
        f"⬆️ High      : ₹{data['high']:.2f}\n"
        f"⬇️ Low       : ₹{data['low']:.2f}\n"
        f"📊 Prev Close: ₹{data['prev_close']:.2f}\n"
        f"🔄 Change    : {sign}{data['pct_change']:.2f}%\n"
        f"📦 Volume    : {data['volume']:,}\n"
        f"📅 52W High  : ₹{data['week52_high']:.2f}\n"
        f"📅 52W Low   : ₹{data['week52_low']:.2f}\n"
    )


def format_swing_message(symbol: str, sig: dict) -> str:
    if "error" in sig:
        return f"⚠️ *{symbol} Swing*: {sig['error']}\n"

    star = "🌟 " if sig["signal"] else ""
    tag  = "✅ VALID SIGNAL" if sig["signal"] else "⬜ Below threshold"

    return (
        f"\n{star}📐 *{symbol} — Swing Signal*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📌 Status    : {tag}\n"
        f"🎯 Score     : {sig['score']}/10  (min {SWING_MIN_SCORE})\n"
        f"📍 Direction : {sig['direction']}\n"
        f"〽️ EMA 20/50 : {sig['ema20']} / {sig['ema50']}\n"
        f"💪 ADX       : {sig['adx']}  {'✅' if sig['adx'] >= ADX_TREND_THRESHOLD else '❌'}\n"
        f"📊 RSI 14    : {sig['rsi']}\n"
        f"📦 Vol Ratio : {sig['vol_ratio']}x  {'✅' if sig['vol_ratio'] >= 1.0 else '❌'}\n"
        f"🛡️ Support   : ₹{sig['support']}\n"
        f"🚧 Resistance: ₹{sig['resistance']}\n"
        f"🛑 Stop Loss : ₹{sig['stop_loss']}\n"
        f"🎯 Target    : ₹{sig['target']}\n"
        f"⚖️ R/R       : 1:{sig['rr']}  {'✅' if sig['rr'] >= SWING_MIN_RR else '❌'}\n"
    )


def format_intraday_message(symbol: str, sig: dict) -> str:
    if not sig.get("active"):
        return f"🕐 *{symbol} Intraday*: {sig.get('reason', 'Inactive')}\n"

    if "error" in sig:
        return f"⚠️ *{symbol} Intraday*: {sig['error']}\n"

    star = "⚡ " if sig["signal"] else ""
    tag  = "✅ VALID SIGNAL" if sig["signal"] else "⬜ Not aligned"

    return (
        f"\n{star}⚡ *{symbol} — Intraday Signal*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📌 Status    : {tag}\n"
        f"🔢 Aligned   : {sig['aligned']}  (all 3 required)\n"
        f"📍 Direction : {sig['direction']}\n"
        f"📏 VWAP      : ₹{sig['vwap']}  {'✅ Above' if sig['above_vwap'] else '❌ Below'}\n"
        f"〽️ EMA 9     : ₹{sig['ema9']}  {'✅ Cross' if sig['ema9_cross'] else '❌ No cross'}\n"
        f"📦 Vol Spike : {sig['vol_ratio']}x  {'✅' if sig['vol_spike'] else '❌'} (min {VOLUME_SPIKE_RATIO}x)\n"
    )


def send_telegram(message: str):
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")
    url       = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload   = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    r = req.post(url, json=payload, timeout=10)
    if not r.ok:
        print(f"⚠️ Telegram error: {r.text}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN JOB
# ══════════════════════════════════════════════════════════════════════════════

def run_job():
    now_str = datetime.now().strftime("%H:%M:%S")
    print(f"[{now_str}] Running market snapshot + signal analysis...")

    try:
        obj = login()
    except Exception as e:
        send_telegram(f"⚠️ Angel One login failed: {e}")
        return

    intraday_active = is_intraday_window()
    header = (
        f"📊 *Market Snapshot — {datetime.now().strftime('%d %b %Y, %H:%M')}*"
        f"{'  _(intraday window)_' if intraday_active else ''}\n\n"
    )

    snapshot_parts = [header]
    signal_parts   = []

    for symbol in WATCHLIST:
        try:
            # Snapshot
            mkt = fetch_market_data(obj, symbol)
            snapshot_parts.append(format_snapshot_message(mkt))
            ltp = mkt["ltp"]
            time.sleep(1)

            # Swing signal (daily candles)
            swing = compute_swing_signal(obj, symbol, ltp)
            signal_parts.append(format_swing_message(symbol, swing))
            time.sleep(1)

            # Intraday signal (5-min candles, gated by time window)
            intra = compute_intraday_signal(obj, symbol, ltp)
            signal_parts.append(format_intraday_message(symbol, intra))
            time.sleep(1)

        except Exception as e:
            snapshot_parts.append(f"⚠️ {symbol}: {e}\n")

    # Send snapshot message
    send_telegram("\n".join(snapshot_parts))
    print("✅ Snapshot sent.")
    time.sleep(2)

    # Send signals message (separate message for readability)
    signal_header = f"🔍 *Signal Analysis — {datetime.now().strftime('%d %b %Y, %H:%M')}*\n"
    send_telegram(signal_header + "\n".join(signal_parts))
    print("✅ Signals sent.")


if __name__ == "__main__":
    run_job()