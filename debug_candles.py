"""
debug_candles.py v5
Uses the confirmed working approach from Angel One forum:
Pass JWT token via access_token into SmartConnect, then use obj.getCandleData()
"""

import os, sys, pyotp
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

try:
    from SmartApi import SmartConnect
except ImportError:
    print("ERROR: pip install smartapi-python"); sys.exit(1)

print("=" * 60)
print("ANGEL ONE CANDLE DEBUGGER v5")
print("=" * 60)

api_key     = os.getenv("ANGEL_API_KEY")
client_id   = os.getenv("ANGEL_CLIENT_ID")
password    = os.getenv("ANGEL_PASSWORD")
totp_secret = os.getenv("ANGEL_TOTP_SECRET")

if not all([api_key, client_id, password, totp_secret]):
    print("ERROR: Fill in .env file"); sys.exit(1)

# Step 1: Login to get JWT
print(f"\n[1] Logging in as {client_id}...")
obj  = SmartConnect(api_key=api_key)
totp = pyotp.TOTP(totp_secret).now()
resp = obj.generateSession(client_id, password, totp)

if not resp.get("status"):
    print(f"LOGIN FAILED: {resp}"); sys.exit(1)

raw_token = resp["data"]["jwtToken"]
# Strip Bearer prefix if present
clean_token = raw_token[7:] if raw_token.startswith("Bearer ") else raw_token
print(f"    Login OK")
print(f"    JWT (clean): {clean_token[:30]}...")

# Step 2: Create NEW SmartConnect object with access_token passed in
# This is the confirmed working approach from Angel One forum
print(f"\n[2] Creating authenticated SmartConnect with access_token...")
obj2 = SmartConnect(api_key=api_key, access_token=clean_token)
print(f"    Done")

# Step 3: Fetch candles using the library method (not direct HTTP)
now       = datetime.now()
from_date = now - timedelta(days=5)

params = {
    "exchange":    "NSE",
    "symboltoken": "2885",
    "interval":    "FIVE_MINUTE",
    "fromdate":    from_date.strftime("%Y-%m-%d %H:%M"),
    "todate":      now.strftime("%Y-%m-%d %H:%M"),
}

print(f"\n[3] Fetching RELIANCE candles via obj.getCandleData()...")
print(f"    From: {params['fromdate']}")
print(f"    To  : {params['todate']}")

try:
    raw = obj2.getCandleData(params)
    print(f"\n[4] Response:")
    print(f"    Status   : {raw.get('status')}")
    print(f"    Message  : {raw.get('message')}")
    print(f"    ErrorCode: {raw.get('errorcode', raw.get('errorCode','none'))}")
    print(f"    Data rows: {len(raw.get('data') or [])}")

    if raw.get("data"):
        print(f"\n    First: {raw['data'][0]}")
        print(f"    Last : {raw['data'][-1]}")
        print(f"\n SUCCESS — working! Run main.py now.")
    else:
        ec = raw.get("errorcode", raw.get("errorCode",""))
        print(f"\n FAILED [{ec}]")
        if ec == "AB1004":
            print(f"""
    CONFIRMED: Your API key and token are correct.
    The issue is that historical data is NOT ENABLED on your account.

    ACTION REQUIRED — send this email:
    To     : smartapi@angelbroking.com
    Subject: Enable Historical Data Access — Client ID {client_id}
    Body   : Please enable getCandleData historical data access for my
             SmartAPI account. Client ID: {client_id}, API Key: {api_key}

    They respond within 1-2 business days.
    Historical data is FREE — it just needs to be enabled.
            """)
        elif ec == "AG8004":
            print(f"""
    AG8004 = Your APP may be set to INACTIVE.

    ACTION REQUIRED:
    1. Go to smartapi.angelone.in
    2. Login → My Apps
    3. Check your app status — must be ACTIVE
    4. If inactive, activate it and try again
    
    Also verify: the API key in your .env matches exactly what's
    shown in the My Apps page (copy-paste, don't retype).
    Your current API key: {api_key}
            """)
        else:
            print(f"    Unknown error. Post this on smartapi.angelone.in/smartapi/forum")
except Exception as e:
    print(f"\n    Exception: {e}")

obj.terminateSession(client_id)
print("=" * 60)
