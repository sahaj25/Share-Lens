import sys
sys.path.append(".")
import os, pyotp
from SmartApi import SmartConnect
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pandas as pd
load_dotenv()

api = SmartConnect(api_key=os.getenv("ANGEL_API_KEY"))
totp = pyotp.TOTP(os.getenv("ANGEL_TOTP_SECRET")).now()
api.generateSession(os.getenv("ANGEL_CLIENT_ID"), os.getenv("ANGEL_PASSWORD"), totp)

end = datetime.now()
start = end - timedelta(days=400)

params = {
    "exchange": "NSE",
    "symboltoken": "2885",
    "interval": "ONE_DAY",
    "fromdate": start.strftime("%Y-%m-%d %H:%M"),
    "todate": end.strftime("%Y-%m-%d %H:%M"),
}

resp = api.getCandleData(params)
candles = resp["data"]
print(f"Candles received: {len(candles)}")
print(f"First: {candles[0][0]}")
print(f"Last: {candles[-1][0]}")