# from load_stocks import get_good_stocks
from load_stocks import get_nifty200_stocks
# ===== CREDENTIALS =====
API_KEY = "9JISPNHk"
CLIENT_ID = "AACF720261"
PASSWORD = "9899"
TOTP_SECRET = "V4NFSKT63GKGOHJXKIDUFK3URI"

# 🔥 Best balance

# STOCKS = get_good_stocks(200)   # ✅ best balance



STOCKS = get_nifty200_stocks()