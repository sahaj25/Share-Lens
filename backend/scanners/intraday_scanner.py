import pandas as pd
from datetime import datetime
from data.angel_api import angel
from indicators.technical import indicators
from config import NIFTY_50_SYMBOLS, MIN_SCORE_TO_ALERT, MIN_RISK_REWARD


class IntradayScanner:

    def __init__(self):
        self.alerted_today = set()  # Track already alerted stocks today
        self.daily_loss = 0         # Track daily loss
        self.daily_loss_limit = 1000

    def scan_all(self):
        """
        Main function — scans all Nifty 50 stocks.
        Runs every 5 minutes between 9:15 AM - 11:00 AM.
        """
        # Check daily loss limit
        if self.daily_loss >= self.daily_loss_limit:
            print("⛔ Daily loss limit hit — intraday scanner stopped")
            return []

        # Check time — only run between 9:15 and 11:00
        now = datetime.now().time()
        start = datetime.strptime("09:15", "%H:%M").time()
        end = datetime.strptime("11:00", "%H:%M").time()

        if not (start <= now <= end):
            print("⏰ Outside intraday trading hours — scanner idle")
            return []

        print(f"⚡ Intraday scan running — {datetime.now().strftime('%H:%M')}")
        opportunities = []

        for symbol in NIFTY_50_SYMBOLS:
            # Skip already alerted stocks today
            if symbol in self.alerted_today:
                continue

            try:
                result = self.analyze_stock(symbol)
                if result:
                    opportunities.append(result)
                    self.alerted_today.add(symbol)
                    print(f"✅ {symbol} — Intraday signal: {result['signal']}")
            except Exception as e:
                print(f"⚠️ {symbol} — Error: {e}")
                continue

        # Sort by score (highest first)
        opportunities.sort(key=lambda x: x["score"], reverse=True)
        return opportunities

    def analyze_stock(self, symbol):
        """
        Analyze a single stock for intraday setup.
        Uses 5-minute candles.
        """
        # FIX: use days=3 instead of days=2
        # Reason: on Mondays or post-holidays, days=2 may only yield 1 trading
        # day of data (~75 candles), which is too few for reliable indicators.
        # days=3 guarantees at least 2 full trading days (~150 candles) even
        # after a long weekend or market holiday.
        df = angel.get_historical_data(
            symbol, interval="FIVE_MINUTE", days=3
        )
        if df is None or len(df) < 20:
            return None

        # Add all indicators
        df = indicators.add_all_indicators(df)

        # Check intraday signal
        signal = indicators.check_intraday_signal(df)
        if signal == "NONE":
            return None

        latest = df.iloc[-1]

        # Calculate score (returns value on 1–10 scale)
        score = self.calculate_score(df, signal)

        # FIX: MIN_SCORE_TO_ALERT must be on a 1–10 scale in config.py
        # e.g. MIN_SCORE_TO_ALERT = 7.0  ← correct
        #      MIN_SCORE_TO_ALERT = 70   ← WRONG, will reject all signals
        if score < MIN_SCORE_TO_ALERT:
            return None

        # Calculate entry, SL, target
        trade_levels = indicators.calculate_sl_target(
            df, signal, risk_reward=2.0
        )
        if not trade_levels:
            return None

        # Reject below minimum R/R
        if trade_levels["risk_reward"] < MIN_RISK_REWARD:
            return None

        return {
            "symbol": symbol,
            "signal": signal,
            "score": score,
            "entry": trade_levels["entry"],
            "stop_loss": trade_levels["stop_loss"],
            "target_1": round(
                trade_levels["entry"] +
                (trade_levels["entry"] - trade_levels["stop_loss"]) * 1.5, 2
            ),
            "target_2": trade_levels["target"],
            "risk_reward": trade_levels["risk_reward"],
            "vwap": round(latest["vwap"], 2),
            "ema_9": round(latest["ema_9"], 2),
            "volume_ratio": round(latest["volume_ratio"], 2),
            "rsi": round(latest["rsi"], 2),
            "time": datetime.now().strftime("%H:%M"),
            "type": "INTRADAY"
        }

    def calculate_score(self, df, signal):
        """
        Score intraday setup on a 1–10 scale.

        Breakdown (out of 100 internally, divided by 10):
          VWAP alignment  → 35 pts
          EMA-9 alignment → 30 pts
          Volume spike    → 35 pts

        ⚠️  Config note: MIN_SCORE_TO_ALERT in config.py must be 1–10
            e.g.  MIN_SCORE_TO_ALERT = 7.0
        """
        score = 0
        latest = df.iloc[-1]
        price = latest["close"]

        # VWAP check — 35 points
        if signal == "BUY" and price > latest["vwap"]:
            score += 35
        elif signal == "SELL" and price < latest["vwap"]:
            score += 35

        # EMA-9 check — 30 points
        if signal == "BUY" and price > latest["ema_9"]:
            score += 30
        elif signal == "SELL" and price < latest["ema_9"]:
            score += 30

        # Volume spike — 35 points
        if latest["volume_spike"]:
            score += 35

        # Convert to 1–10 scale
        return round(score / 10, 1)

    def reset_daily(self):
        """
        Reset daily tracking.
        Called every morning at 9:00 AM by scheduler.
        """
        self.alerted_today = set()
        self.daily_loss = 0
        print("🔄 Intraday scanner reset for new day")

    def update_daily_loss(self, loss_amount):
        """
        Update daily loss tracker.
        Called when a trade hits stop loss.
        """
        self.daily_loss += loss_amount
        print(f"📉 Daily loss updated: ₹{self.daily_loss}")

        if self.daily_loss >= self.daily_loss_limit:
            print("⛔ Daily loss limit reached — no more intraday trades today")


# Single instance
intraday_scanner = IntradayScanner()