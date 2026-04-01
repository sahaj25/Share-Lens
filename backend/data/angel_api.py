import os
import pyotp
from SmartApi import SmartConnect
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime, timedelta
import time

load_dotenv()

# Nifty 50 stocks with their Angel One token numbers
NIFTY50_STOCKS = {
    "RELIANCE":   "2885",
    "TCS":        "11536",
    "HDFCBANK":   "1333",
    "BHARTIARTL": "10604",
    "ICICIBANK":  "4963",
    "INFOSYS":    "1594",
    "SBIN":       "3045",
    "HINDUNILVR": "1394",
    "ITC":        "1660",
    "LT":         "11483",
    "KOTAKBANK":  "1922",
    "AXISBANK":   "5900",
    "WIPRO":      "3787",
    "ASIANPAINT": "236",
    "MARUTI":     "10999",
    "SUNPHARMA":  "3351",
    "ULTRACEMCO": "11532",
    "TITAN":      "3506",
    "BAJFINANCE": "317",
    "NESTLEIND":  "17963",
    "POWERGRID":  "14977",
    "NTPC":       "11630",
    "TATAMOTORS": "3499",
    "HCLTECH":    "7229",
    "M&M":        "2031",
    "ADANIENT":   "25",
    "ADANIPORTS": "15083",
    "COALINDIA":  "1624",
    "ONGC":       "2475",
    "JSWSTEEL":   "11723",
    "TATASTEEL":  "3408",
    "HINDALCO":   "1363",
    "BAJAJFINSV": "16675",
    "BAJAJ-AUTO": "16669",
    "HEROMOTOCO": "1348",
    "EICHERMOT":  "910",
    "DRREDDY":    "881",
    "DIVISLAB":   "10940",
    "CIPLA":      "694",
    "APOLLOHOSP": "157",
    "BRITANNIA":  "547",
    "TATACONSUM": "3432",
    "GRASIM":     "1232",
    "SHRIRAMFIN": "4306",
    "BEL":        "383",
    "INDUSINDBK": "5258",
    "SBILIFE":    "21808",
    "HDFCLIFE":   "467",
    "TECHM":      "13538",
    "BPCL":       "526",
}


def login():
    """Login to Angel One and return SmartAPI object"""
    try:
        api = SmartConnect(api_key=os.getenv("ANGEL_API_KEY"))
        
        totp = pyotp.TOTP(os.getenv("ANGEL_TOTP_SECRET")).now()
        
        data = api.generateSession(
            os.getenv("ANGEL_CLIENT_ID"),
            os.getenv("ANGEL_PASSWORD"),
            totp
        )
        
        if data["status"] == False:
            print(f"Login failed: {data['message']}")
            return None
            
        print("Angel One login successful")
        return api
        
    except Exception as e:
        print(f"Login error: {e}")
        return None


def fetch_candles(api, symbol, token, days=100):
    """Fetch daily OHLCV candles for a single stock"""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        params = {
            "exchange": "NSE",
            "symboltoken": token,
            "interval": "ONE_DAY",
            "fromdate": start_date.strftime("%Y-%m-%d %H:%M"),
            "todate": end_date.strftime("%Y-%m-%d %H:%M"),
        }
        
        response = api.getCandleData(params)
        
        if response["status"] == False:
            print(f"Failed to fetch {symbol}: {response['message']}")
            return None
        
        candles = response["data"]
        
        if not candles or len(candles) < 50:
            print(f"Not enough data for {symbol}")
            return None
        
        df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp")
        df = df.astype({"open": float, "high": float, "low": float, "close": float, "volume": float})
        df["symbol"] = symbol
        
        return df
        
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None


def fetch_all_stocks():
    """Login and fetch data for all 50 Nifty stocks"""
    api = login()
    if not api:
        return None
    
    all_data = {}
    failed = []
    
    print(f"Fetching data for {len(NIFTY50_STOCKS)} stocks...")
    
    for symbol, token in NIFTY50_STOCKS.items():
        df = fetch_candles(api, symbol, token)
        
        if df is not None:
            all_data[symbol] = df
            print(f"  ✓ {symbol} — {len(df)} candles")
        else:
            failed.append(symbol)
            print(f"  ✗ {symbol} — failed")
        
        # Small delay to avoid hitting rate limits
        time.sleep(0.3)
    
    print(f"\nFetched: {len(all_data)}/50 stocks")
    if failed:
        print(f"Failed: {failed}")
    
    return all_data


# Quick test
if __name__ == "__main__":
    data = fetch_all_stocks()
    
    if data:
        # Verify one stock
        sample = data["RELIANCE"]
        print("\nRELIANCE sample data (last 5 candles):")
        print(sample.tail())
        print(f"\nColumns: {list(sample.columns)}")
        print(f"Date range: {sample.index[0]} to {sample.index[-1]}")