"""
Angel One SmartAPI - Data Fetching Module
Handles login, token refresh, and historical/live candle data
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
import time

IST = pytz.timezone("Asia/Kolkata")

# ── Try importing SmartAPI (graceful fallback to demo mode) ──
try:
    from SmartApi import SmartConnect
    import pyotp
    SMARTAPI_AVAILABLE = True
except ImportError:
    SMARTAPI_AVAILABLE = False


class AngelOneClient:
    def __init__(self, api_key: str, client_id: str, password: str, totp_secret: str):
        self.api_key = api_key
        self.client_id = client_id
        self.password = password
        self.totp_secret = totp_secret
        self.obj = None
        self.auth_token = None
        self.connected = False
        self.demo_mode = not SMARTAPI_AVAILABLE

    def connect(self) -> tuple[bool, str]:
        """Login and obtain auth token"""
        if self.demo_mode:
            self.connected = True
            return True, "DEMO MODE — SmartAPI not installed. Run: pip install smartapi-python pyotp"

        try:
            totp = pyotp.TOTP(self.totp_secret).now()
            self.obj = SmartConnect(api_key=self.api_key)
            data = self.obj.generateSession(self.client_id, self.password, totp)

            if data["status"]:
                self.auth_token = data["data"]["jwtToken"]
                self.connected = True
                return True, f"Connected as {self.client_id}"
            else:
                return False, data.get("message", "Login failed")
        except Exception as e:
            return False, str(e)

    def get_candles(self, symbol_token: str, symbol: str,
                    interval: str = "ONE_MINUTE",
                    lookback_minutes: int = 120) -> pd.DataFrame | None:
        """
        Fetch OHLCV candles for a symbol.
        interval: ONE_MINUTE | THREE_MINUTE | FIVE_MINUTE | TEN_MINUTE | FIFTEEN_MINUTE
        """
        if self.demo_mode or not self.connected:
            return self._generate_demo_data(symbol, lookback_minutes)

        try:
            now = datetime.now(IST)
            from_dt = now - timedelta(minutes=lookback_minutes)

            params = {
                "exchange": "NSE",
                "symboltoken": symbol_token,
                "interval": interval,
                "fromdate": from_dt.strftime("%Y-%m-%d %H:%M"),
                "todate": now.strftime("%Y-%m-%d %H:%M"),
            }

            resp = self.obj.getCandleData(params)
            if resp["status"] and resp["data"]:
                df = pd.DataFrame(resp["data"],
                                  columns=["timestamp", "open", "high", "low", "close", "volume"])
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df = df.set_index("timestamp").tz_convert(IST)
                for col in ["open", "high", "low", "close", "volume"]:
                    df[col] = pd.to_numeric(df[col])
                return df
            return None
        except Exception as e:
            print(f"[AngelOne] Error fetching {symbol}: {e}")
            return None

    def get_ltp(self, exchange: str, symbol: str, symbol_token: str) -> float | None:
        """Get last traded price"""
        if self.demo_mode or not self.connected:
            return None
        try:
            data = self.obj.ltpData(exchange, symbol, symbol_token)
            if data["status"]:
                return float(data["data"]["ltp"])
        except Exception:
            return None

    # ─────────────────────────────────────
    # Demo / Offline Mode
    # ─────────────────────────────────────
    def _generate_demo_data(self, symbol: str, minutes: int = 120) -> pd.DataFrame:
        """
        Synthetic OHLCV data seeded by symbol name for offline testing.
        Produces realistic intraday price paths.
        """
        rng = np.random.default_rng(abs(hash(symbol)) % (2**32))
        now = datetime.now(IST).replace(second=0, microsecond=0)

        # Start from 9:15 AM today
        start = now.replace(hour=9, minute=15)
        candle_count = min(minutes, max(30, int((now - start).seconds / 60) + 1))

        base_price = rng.uniform(200, 3000)
        returns = rng.normal(0.0003, 0.002, candle_count)
        closes = base_price * np.cumprod(1 + returns)

        opens, highs, lows, volumes = [], [], [], []
        for i, c in enumerate(closes):
            o = closes[i - 1] if i > 0 else c * rng.uniform(0.999, 1.001)
            h = max(o, c) * rng.uniform(1.0, 1.003)
            l = min(o, c) * rng.uniform(0.997, 1.0)
            v = int(rng.integers(10000, 500000))
            opens.append(o); highs.append(h); lows.append(l); volumes.append(v)

        timestamps = [start + timedelta(minutes=i) for i in range(candle_count)]
        df = pd.DataFrame({
            "open": opens, "high": highs, "low": lows,
            "close": closes, "volume": volumes
        }, index=pd.DatetimeIndex(timestamps, tz=IST))
        df.index.name = "timestamp"
        return df


# ─────────────────────────────────────────
# Symbol Token Lookup
# Downloads Angel One's full NSE symbol master
# and caches it locally as symbol_master.csv
# ─────────────────────────────────────────

SYMBOL_MASTER_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
SYMBOL_MASTER_CACHE = "symbol_master.csv"

# Fallback hardcoded tokens (used if download fails)
_FALLBACK_TOKENS = {
    "RELIANCE":    "2885",
    "TCS":         "11536",
    "INFY":        "1594",
    "HDFCBANK":    "1333",
    "ICICIBANK":   "4963",
    "SBIN":        "3045",
    "TATAMOTORS":  "3432",
    "WIPRO":       "3787",
    "AXISBANK":    "5900",
    "BAJFINANCE":  "317",
    "NIFTY":       "26000",
    "BANKNIFTY":   "26009",
    # Extended watchlist
    "ADANIPOWER":  "467",
    "IOC":         "1624",
    "IRFC":        "543257",
    "GAIL":        "910",
    "CANBK":       "4668",
    "IDBI":        "14978",
    "PNB":         "14977",
    "UNIONBANK":   "2752",
    "BANKINDIA":   "547",
    "IOB":         "4514",
    "SUZLON":      "3103",
    "NHPC":        "533098",
    "IDEA":        "14366",
    "RPOWER":      "3812",
    "JPPOWER":     "533152",
    "HUDCO":       "5253",
    "SJVN":        "533206",
    "NBCC":        "534309",
    "BHEL":        "438",
    "CASTROLIND":  "558",
    "HFCL":        "1063",
    "GSFC":        "953",
    "HINDCOPPER":  "543775",
    "SCI":         "4195",
    "RVNL":        "543544",
    "OLAELEC":     "543888",
}

# In-memory cache after first load
_symbol_master_df: pd.DataFrame | None = None


def _load_symbol_master() -> pd.DataFrame | None:
    """Load symbol master from local cache or download fresh."""
    global _symbol_master_df
    if _symbol_master_df is not None:
        return _symbol_master_df

    import os, json
    from datetime import date

    # Use cache if it exists and was created today
    if os.path.exists(SYMBOL_MASTER_CACHE):
        cache_date = datetime.fromtimestamp(os.path.getmtime(SYMBOL_MASTER_CACHE)).date()
        if cache_date == date.today():
            try:
                _symbol_master_df = pd.read_csv(SYMBOL_MASTER_CACHE, dtype=str)
                return _symbol_master_df
            except Exception:
                pass

    # Download fresh
    try:
        import urllib.request
        print(f"[INFO] Downloading Angel One symbol master...")
        with urllib.request.urlopen(SYMBOL_MASTER_URL, timeout=10) as r:
            data = json.loads(r.read().decode())
        df = pd.DataFrame(data)
        df.to_csv(SYMBOL_MASTER_CACHE, index=False)
        _symbol_master_df = df
        print(f"[INFO] Symbol master loaded: {len(df)} symbols cached.")
        return df
    except Exception as e:
        print(f"[WARN] Could not download symbol master: {e}")
        # Last resort — use any existing cache even if stale
        if os.path.exists(SYMBOL_MASTER_CACHE):
            try:
                _symbol_master_df = pd.read_csv(SYMBOL_MASTER_CACHE, dtype=str)
                print(f"[INFO] Using stale symbol master cache ({len(_symbol_master_df)} symbols)")
                return _symbol_master_df
            except Exception:
                pass
        return None


def get_token(symbol: str) -> tuple[str, str]:
    """
    Returns (token, symbol_name) for a given symbol string.
    Searches Angel One's full symbol master for NSE EQ instruments.
    Falls back to hardcoded list if master is unavailable.
    Raises ValueError with helpful message if symbol is not found.
    """
    sym = symbol.upper().strip()

    # Try full symbol master first
    master = _load_symbol_master()
    if master is not None:
        # Filter to NSE cash segment only
        nse = master[
            (master["exch_seg"].str.upper() == "NSE") &
            (master["instrumenttype"].str.upper().isin(["", "EQ"]) |
             master["symbol"].str.endswith("-EQ"))
        ]

        # Exact match on symbol (e.g. "OLAELEC-EQ" or "OLAELEC")
        match = nse[nse["symbol"].str.upper().str.replace("-EQ", "") == sym]

        if match.empty:
            # Try name contains match as fallback
            match = nse[nse["name"].str.upper().str.contains(sym, na=False)]

        if not match.empty:
            row = match.iloc[0]
            token = str(row["token"])
            name = str(row.get("name", sym))
            return token, name

        # Symbol not found — give helpful suggestions
        suggestions = nse[
            nse["symbol"].str.upper().str.contains(sym[:4], na=False)
        ]["symbol"].str.replace("-EQ", "").head(5).tolist()

        hint = f"  Did you mean: {', '.join(suggestions)}" if suggestions else ""
        raise ValueError(
            f"Symbol '{symbol}' not found in NSE symbol master.{hint}\n"
            f"  Tip: Use the exact NSE trading symbol (e.g. OLAELEC, not OLA)"
        )

    # Fallback to hardcoded list
    if sym in _FALLBACK_TOKENS:
        return _FALLBACK_TOKENS[sym], sym

    raise ValueError(
        f"Symbol '{symbol}' not found. Symbol master download failed and it's not in the fallback list.\n"
        f"  Available fallback symbols: {', '.join(_FALLBACK_TOKENS.keys())}"
    )