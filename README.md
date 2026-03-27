# Trading Signal Bot
Rules-based intraday + swing scanner. No AI. No fluff. Just signals.

---

## What this does
- Scans your watchlist every 5 minutes during market hours
- Sends BUY signals to Telegram when ALL 4 conditions pass
- Logs every signal to CSV (open in Excel)
- Runs fully automatically once started

## What this does NOT do
- It does NOT place trades automatically
- It does NOT guarantee profit
- It is NOT a get-rich-quick system

---

## Setup (one time, ~15 minutes)

### Step 1 — Install Python 3.11+
Download from https://python.org

### Step 2 — Install dependencies
```
pip install -r requirements.txt
```

### Step 3 — Create your .env file
```
copy .env.example .env        (Windows)
cp .env.example .env          (Mac/Linux)
```
Open .env and fill in:
- ANGEL_API_KEY       → from Angel One SmartAPI developer portal
- ANGEL_CLIENT_ID     → your Angel One login ID
- ANGEL_PASSWORD      → your Angel One password
- ANGEL_TOTP_SECRET   → from Angel One TOTP setup (NOT the 6-digit code, the secret key)
- TELEGRAM_BOT_TOKEN  → from @BotFather on Telegram
- TELEGRAM_CHAT_ID    → your personal chat ID (message @userinfobot)

### Step 4 — Test your connections
```
python main.py --test
```
You should see:
  Telegram: ✓ OK
  Angel One: ✓ OK

### Step 5 — Run the bot
```
python main.py
```
The bot will wait until 8:30 AM and start automatically.

---

## How to get your credentials

### Angel One SmartAPI
1. Log in to angelone.in
2. Go to My Profile → API
3. Create an app → copy API Key
4. Enable TOTP → copy the SECRET KEY (not the 6-digit code)

### Telegram Bot
1. Open Telegram → search @BotFather
2. Send /newbot → follow instructions
3. Copy the token it gives you
4. Message @userinfobot to get your chat ID

---

## Running a scan immediately (for testing)
```
python main.py --intraday-now    # run intraday scan right now
python main.py --swing-now       # run swing scan right now
```

---

## Signal logic (what generates a BUY)

### Intraday (5-min chart)
All 4 must pass:
1. Price above VWAP
2. Volume ≥ 2x 20-period average
3. Price breaks above 20-period resistance
4. RSI between 50 and 75

### Swing (daily chart)
All 4 must pass:
1. Price above EMA20 AND EMA20 above EMA50 (uptrend)
2. Volume ≥ 1.5x average
3. Price breaks above 20-period resistance
4. RSI between 45 and 70

---

## Telegram message format
```
🟢 BUY SIGNAL — RELIANCE
──────────────────────────────
🏷️  Type:       INTRADAY
💰 Entry:      ₹2450.00
🛑 Stop Loss:  ₹2437.75
🎯 Target:     ₹2486.75
⚖️  R:R Ratio:  1:2.9
──────────────────────────────
📈 RSI:        62.4
📊 Volume:     3.2x avg
📉 Trend:      UP
──────────────────────────────
💡 Why:
Above VWAP (2441) | Vol spike 3.2x | Breakout above 2448 | RSI 62.4
──────────────────────────────
🕐 25 Mar 2025  11:35:00
📊 PAPER TRADE
```

---

## Files
```
trading-tool/
├── main.py                  ← START HERE
├── requirements.txt
├── .env.example             ← copy to .env
├── config/settings.py       ← edit your watchlist + strategy settings
├── data/angel_api.py        ← Angel One connection
├── indicators/technical.py  ← VWAP, RSI, EMA, Volume calc
├── signals/engine.py        ← the 4-condition buy logic
├── alerts/telegram_bot.py   ← Telegram messages
├── scanners/scanner.py      ← scan loop
└── logs/
    ├── signal_logger.py     ← CSV logging
    └── signals.csv          ← your signal history (auto-created)
```

---

## Paper trading (recommended for first 4-6 weeks)
PAPER_TRADING=true in your .env
- All signals are marked "PAPER TRADE"
- Nothing is executed
- You manually check if the signal would have been profitable

After 50+ signals, check your win rate in signals.csv before using real money.

---

## Customise your watchlist
Edit config/settings.py
- Add/remove stocks from INTRADAY_WATCHLIST or SWING_WATCHLIST
- Find the Angel One token for any stock at:
  https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json

---

## Common errors

| Error | Fix |
|---|---|
| Angel One login failed | Check API key, client ID, password in .env |
| TOTP error | Use the SECRET KEY from Angel One, not the 6-digit code |
| Telegram not sending | Check bot token and chat ID |
| No signals generated | Normal — conditions are strict. Run --intraday-now to test |
| ModuleNotFoundError | Run: pip install -r requirements.txt |
