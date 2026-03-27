

import os
import sys
import pyotp
import time
from SmartApi import SmartConnect
import schedule
from datetime import datetime
import asyncio
import requests as req

API_KEY = os.getenv("ANGEL_API_KEY")
CLIENT_ID = os.getenv("ANGEL_CLIENT_ID")
PASSWORD = os.getenv("ANGEL_PASSWORD")
TOTP_TOKEN = os.getenv("ANGEL_TOTP_TOKEN")


# ── Set your daily schedule times here ───────────────────────────────────────

SCHEDULE_TIMES = ["00:07", "13:00", "15:30"]  # 24hr format, add as many as you want

# ── Symbols to track ──────────────────────────────────────────────────────────

WATCHLIST = ["RELIANCE", "TCS", "SBIN"]

SYMBOL_TOKEN_MAP = {

    "RELIANCE": "2885", "TCS": "11536", "INFY": "1594",

    "HDFCBANK": "1333", "ICICIBANK": "4963", "SBIN": "3045",

    "HINDUNILVR": "1394", "ITC": "1660", "KOTAKBANK": "1922",

    "LT": "11483", "BAJFINANCE": "317", "AXISBANK": "5900",

    "MARUTI": "10999", "WIPRO": "3787", "HCLTECH": "7229",

    "TITAN": "3506", "NESTLEIND": "17963", "ADANIENT": "25",

    "ULTRACEMCO": "11532", "POWERGRID": "14977",

}


def login() -> SmartConnect:
    obj = SmartConnect(api_key=API_KEY)

    totp = pyotp.TOTP(TOTP_TOKEN).now()

    data = obj.generateSession(CLIENT_ID, PASSWORD, totp)

    if data["status"] is False:
        raise RuntimeError(f"Login failed: {data['message']}")

    return obj


def get_token(symbol: str) -> str:
    token = SYMBOL_TOKEN_MAP.get(symbol.upper())

    if token:
        return token

    url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"

    master = req.get(url, timeout=10).json()

    for item in master:

        if item.get("symbol") == symbol.upper() and item.get("exch_seg") == "NSE":
            return item["token"]

    raise ValueError(f"Token not found for symbol: {symbol}")


def fetch_market_data(obj: SmartConnect, symbol: str) -> dict:
    token = get_token(symbol)

    resp = obj.getMarketData("FULL", {"NSE": [token]})

    if resp["status"] is False:
        raise RuntimeError(f"getMarketData failed: {resp['message']}")

    fetched = resp["data"].get("fetched", [])

    if not fetched:
        raise RuntimeError(f"No data returned for {symbol}")

    d = fetched[0]

    ltp = float(d.get("ltp", 0))

    prev_close = float(d.get("close", 0))

    pct_change = ((ltp - prev_close) / prev_close * 100) if prev_close else 0.0

    return {

        "symbol": symbol.upper(),

        "ltp": ltp,

        "open": float(d.get("open", 0)),

        "high": float(d.get("high", 0)),

        "low": float(d.get("low", 0)),

        "prev_close": prev_close,

        "pct_change": round(pct_change, 2),

        "volume": int(d.get("tradeVolume", 0)),

        "week52_high": float(d.get("fiftyTwoWeekHighPrice", 0)),

        "week52_low": float(d.get("fiftyTwoWeekLowPrice", 0)),

    }


def format_telegram_message(data: dict) -> str:
    arrow = "🟢" if data["pct_change"] >= 0 else "🔴"

    sign = "+" if data["pct_change"] >= 0 else ""

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


def send_telegram(message: str):
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,

        "text": message,

        "parse_mode": "Markdown"

    }

    r = req.post(url, json=payload, timeout=10)

    if not r.ok:
        print(f"Telegram error: {r.text}")


def run_job():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Running market snapshot...")

    try:

        obj = login()

    except Exception as e:

        send_telegram(f"⚠️ Angel One login failed: {e}")

        return

    header = f"📊 *Market Snapshot — {datetime.now().strftime('%d %b %Y, %H:%M')}*\n\n"

    messages = [header]

    for symbol in WATCHLIST:

        try:

            data = fetch_market_data(obj, symbol)

            messages.append(format_telegram_message(data))

            time.sleep(1)  # avoid rate limit

        except Exception as e:

            messages.append(f"⚠️ {symbol}: {e}\n")

    full_message = "\n".join(messages)

    send_telegram(full_message)

    print("Sent to Telegram.")


if __name__ == "__main__":
    run_job()
