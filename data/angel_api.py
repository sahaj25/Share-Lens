import SmartApi
import pyotp
import pandas as pd
from SmartApi.smartConnect import SmartConnect
from config import (
    ANGEL_API_KEY,
    ANGEL_CLIENT_ID,
    ANGEL_PASSWORD,
    ANGEL_TOTP_SECRET
)


class AngelOneAPI:
    def __init__(self):
        self.api = None
        self.session = None

    def login(self):
        try:
            self.api = SmartConnect(api_key=ANGEL_API_KEY)
            totp = pyotp.TOTP(ANGEL_TOTP_SECRET).now()
            self.session = self.api.generateSession(
                ANGEL_CLIENT_ID,
                ANGEL_PASSWORD,
                totp
            )
            print("✅ Angel One login successful")
            return True
        except Exception as e:
            print(f"❌ Angel One login failed: {e}")
            return False

    def get_historical_data(self, symbol, interval="ONE_DAY", days=100):
        """
        Fetch historical OHLCV data for a symbol
        interval options:
        → ONE_DAY (daily candles — for swing)
        → FIVE_MINUTE (5 min candles — for intraday)
        """
        try:
            from datetime import datetime, timedelta
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            token = self.get_token(symbol)
            if not token:
                return None

            params = {
                "exchange": "NSE",
                "symboltoken": token,
                "interval": interval,
                "fromdate": start_date.strftime("%Y-%m-%d %H:%M"),
                "todate": end_date.strftime("%Y-%m-%d %H:%M")
            }

            response = self.api.getCandleData(params)

            if response["status"] and response["data"]:
                df = pd.DataFrame(
                    response["data"],
                    columns=["timestamp", "open", "high", "low", "close", "volume"]
                )
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df.set_index("timestamp", inplace=True)
                df = df.astype(float)
                return df
            else:
                print(f"❌ No data for {symbol}")
                return None

        except Exception as e:
            print(f"❌ Error fetching data for {symbol}: {e}")
            return None

    def get_live_price(self, symbol):
        """Get current live price of a symbol"""
        try:
            token = self.get_token(symbol)
            if not token:
                return None

            response = self.api.ltpData("NSE", symbol, token)
            if response["status"]:
                return response["data"]["ltp"]
            return None

        except Exception as e:
            print(f"❌ Error fetching live price for {symbol}: {e}")
            return None

    def get_token(self, symbol):
        """Get Angel One token for a symbol"""
        # Token map for Nifty 50 stocks
        token_map = {
            "RELIANCE": "2885", "TCS": "11536", "HDFCBANK": "1333",
            "INFY": "1594", "ICICIBANK": "4963", "HINDUNILVR": "1394",
            "ITC": "1660", "SBIN": "3045", "BHARTIARTL": "10604",
            "KOTAKBANK": "1922", "LT": "11483", "AXISBANK": "5900",
            "ASIANPAINT": "236", "MARUTI": "10999", "TITAN": "3506",
            "SUNPHARMA": "3351", "ULTRACEMCO": "11532", "BAJFINANCE": "317",
            "WIPRO": "3787", "NESTLEIND": "17963", "POWERGRID": "14977",
            "NTPC": "11630", "TECHM": "13538", "TATAMOTORS": "3456",
            "HCLTECH": "7229", "BAJAJFINSV": "16675", "ONGC": "2475",
            "JSWSTEEL": "11723", "TATASTEEL": "3499", "ADANIENT": "25",
            "ADANIPORTS": "15083", "COALINDIA": "20374", "DIVISLAB": "10940",
            "DRREDDY": "881", "EICHERMOT": "910", "GRASIM": "1232",
            "HEROMOTOCO": "1348", "HINDALCO": "1363", "INDUSINDBK": "5258",
            "M&M": "2031", "BRITANNIA": "547", "CIPLA": "694",
            "APOLLOHOSP": "157", "BAJAJ-AUTO": "16669", "BPCL": "526",
            "TATACONSUM": "3432", "UPL": "11287", "VEDL": "3063",
            "SHREECEM": "3103", "SBILIFE": "21808"
        }
        return token_map.get(symbol)

    def logout(self):
        try:
            self.api.terminateSession(ANGEL_CLIENT_ID)
            print("✅ Angel One logout successful")
        except Exception as e:
            print(f"❌ Logout error: {e}")


# Single instance to reuse across the app
angel = AngelOneAPI()



if __name__ == "__main__":
    angel.login()
    data = angel.get_historical_data("RELIANCE")
    print(data.tail())
    angel.logout()