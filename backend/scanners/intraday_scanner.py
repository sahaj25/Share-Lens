import pandas as pd
from datetime import datetime
from data.angel_api import angel
from indicators.technical import indicators
from config import NIFTY_50_SYMBOLS, MIN_SCORE_TO_ALERT, MIN_RISK_REWARD


class IntradayScanner:

    def __init__(self):
        self.alerted_today = set()
        self.daily_loss = 0
        self.daily_loss_limit = 1000
        self.active_trades = []   # ✅ NEW

    def scan_all(self):
        """
        Runs every 5 min (9:15–11:00)
        """
        if self.daily_loss >= self.daily_loss_limit:
            print("⛔ Daily loss limit hit — scanner stopped")
            return []

        now = datetime.now().time()
        start = datetime.strptime("09:15", "%H:%M").time()
        end = datetime.strptime("11:00", "%H:%M").time()

        if not (start <= now <= end):
            print("⏰ Outside trading hours")
            return []

        print(f"⚡ Scan running — {datetime.now().strftime('%H:%M')}")
        opportunities = []

        for symbol in NIFTY_50_SYMBOLS:

            if symbol in self.alerted_today:
                continue

            try:
                result = self.analyze_stock(symbol)

                if result:
                    opportunities.append(result)
                    self.alerted_today.add(symbol)

                    print(f"✅ {symbol} — {result['signal']}")

            except Exception as e:
                print(f"⚠️ {symbol} — {e}")
                continue

        opportunities.sort(key=lambda x: x["score"], reverse=True)
        return opportunities

    def analyze_stock(self, symbol):

        df = angel.get_historical_data(
            symbol, interval="FIVE_MINUTE", days=2
        )

        if df is None or len(df) < 20:
            return None

        df = indicators.add_all_indicators(df)

        signal = indicators.check_intraday_signal(df)
        if signal == "NONE":
            return None

        latest = df.iloc[-1]
        score = self.calculate_score(df, signal)

        if score < MIN_SCORE_TO_ALERT:
            return None

        trade_levels = indicators.calculate_sl_target(
            df, signal, risk_reward=2.0
        )

        if not trade_levels:
            return None

        if trade_levels["risk_reward"] < MIN_RISK_REWARD:
            return None

        # ✅ STORE ACTIVE TRADE
        trade = {
            "symbol": symbol,
            "signal": signal,
            "entry": trade_levels["entry"],
            "stop_loss": trade_levels["stop_loss"],
            "target": trade_levels["target"],
            "status": "OPEN"
        }
        self.active_trades.append(trade)

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

    def monitor_positions(self):
        """
        Runs every 1–2 minutes
        """

        # ✅ Stop everything if max loss hit
        if self.daily_loss >= self.daily_loss_limit:
            print("⛔ Max loss hit — closing all trades")

            for trade in self.active_trades:
                trade["status"] = "CLOSED"

            return

        for trade in self.active_trades:

            if trade["status"] != "OPEN":
                continue

            try:
                ltp = angel.get_ltp(trade["symbol"])
                if not ltp:
                    continue

                entry = trade["entry"]
                sl = trade["stop_loss"]
                target = trade["target"]

                # BUY
                if trade["signal"] == "BUY":

                    if ltp <= sl:
                        loss = abs(entry - sl)   # ✅ FIXED
                        self.update_daily_loss(loss)

                        trade["status"] = "CLOSED"
                        print(f"❌ SL HIT: {trade['symbol']} ₹{loss}")

                    elif ltp >= target:
                        trade["status"] = "CLOSED"
                        print(f"🎯 TARGET HIT: {trade['symbol']}")

                # SELL
                elif trade["signal"] == "SELL":

                    if ltp >= sl:
                        loss = abs(entry - sl)   # ✅ FIXED
                        self.update_daily_loss(loss)

                        trade["status"] = "CLOSED"
                        print(f"❌ SL HIT: {trade['symbol']} ₹{loss}")

                    elif ltp <= target:
                        trade["status"] = "CLOSED"
                        print(f"🎯 TARGET HIT: {trade['symbol']}")

            except Exception as e:
                print(f"⚠️ Monitor error {trade['symbol']}: {e}")

    def calculate_score(self, df, signal):

        score = 0
        latest = df.iloc[-1]
        price = latest["close"]

        if signal == "BUY" and price > latest["vwap"]:
            score += 35
        elif signal == "SELL" and price < latest["vwap"]:
            score += 35

        if signal == "BUY" and price > latest["ema_9"]:
            score += 30
        elif signal == "SELL" and price < latest["ema_9"]:
            score += 30

        if latest["volume_spike"]:
            score += 35

        return round(score / 10, 1)

    def reset_daily(self):
        self.alerted_today = set()
        self.daily_loss = 0
        self.active_trades = []   # ✅ RESET
        print("🔄 Reset for new day")

    def update_daily_loss(self, loss_amount):
        self.daily_loss += loss_amount

        print(f"📉 Daily loss: ₹{self.daily_loss}")

        if self.daily_loss >= self.daily_loss_limit:
            print("⛔ Daily loss limit reached — stopping trading")


# Single instance
intraday_scanner = IntradayScanner()