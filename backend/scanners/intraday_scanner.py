import pandas as pd
from datetime import datetime
from data.angel_api import angel
from indicators.technical import indicators
from config import NIFTY_50_SYMBOLS, MIN_SCORE_TO_ALERT, MIN_RISK_REWARD


class IntradayScanner:

    def __init__(self):
        self.alerted_today = set()  # Track already alerted stocks today
        self.daily_loss = 0  # Track daily loss
        self.daily_loss_limit = 1000

    def scan_all(self):
        """
        Main function — scans all Nifty 50 stocks
        Runs every 5 minutes between 9:15 AM - 11:00 AM
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

        # Sort by score
        opportunities.sort(key=lambda x: x["score"], reverse=True)
        return opportunities

    def analyze_stock(self, symbol):
        """
        Analyze a single stock for intraday setup
        Uses 5-minute candles
        """
        # Fetch 5 minute candle data
        df = angel.get_historical_data(
            symbol, interval="FIVE_MINUTE", days=2
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

        # Calculate score
        score = self.calculate_score(df, signal)

        # Reject below threshold
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
        Score intraday setup out of 10
        VWAP + EMA9 + Volume = 3 core conditions
        """
        score = 0
        latest = df.iloc[-1]
        price = latest["close"]

        # VWAP check — 35 points
        if signal == "BUY" and price > latest["vwap"]:
            score += 35
        elif signal == "SELL" and price < latest["vwap"]:
            score += 35

        # EMA 9 check — 30 points
        if signal == "BUY" and price > latest["ema_9"]:
            score += 30
        elif signal == "SELL" and price < latest["ema_9"]:
            score += 30

        # Volume spike — 35 points
        if latest["volume_spike"]:
            score += 35

        # Convert to 1-10 scale
        return round(score / 10, 1)

    def reset_daily(self):
        """
        Reset daily tracking
        Called every morning at 9:00 AM by scheduler
        """
        self.alerted_today = set()
        self.daily_loss = 0
        print("🔄 Intraday scanner reset for new day")

    def update_daily_loss(self, loss_amount):
        """
        Update daily loss tracker
        Called when a trade hits stop loss
        """
        self.daily_loss += loss_amount
        print(f"📉 Daily loss updated: ₹{self.daily_loss}")

        if self.daily_loss >= self.daily_loss_limit:
            print("⛔ Daily loss limit reached — no more intraday trades today")


# Single instance
intraday_scanner = IntradayScanner()