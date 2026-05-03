from SmartApi import SmartConnect
import pyotp
import pandas as pd
from datetime import datetime, timedelta
from config import API_KEY, CLIENT_ID, PASSWORD, TOTP_SECRET

class AngelAPI:
    def __init__(self):
        self.obj = SmartConnect(api_key=API_KEY)
        totp = pyotp.TOTP(TOTP_SECRET).now()
        self.obj.generateSession(CLIENT_ID, PASSWORD, totp)

    def get_data(self, token):
        today = datetime.now()
        from_date = (today - timedelta(days=365)).strftime("%Y-%m-%d 09:15")
        to_date = today.strftime("%Y-%m-%d 15:30")

        params = {
            "exchange": "NSE",
            "symboltoken": token,
            "interval": "ONE_DAY",
            "fromdate": from_date,
            "todate": to_date
        }

        data = self.obj.getCandleData(params)

        if not data or "data" not in data or data["data"] is None:
            return pd.DataFrame()

        df = pd.DataFrame(
            data["data"],
            columns=["time", "open", "high", "low", "close", "volume"]
        )

        df[["open", "high", "low", "close", "volume"]] = \
            df[["open", "high", "low", "close", "volume"]].astype(float)

        return df