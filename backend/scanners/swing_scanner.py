import pandas as pd
from data.angel_api import angel
from indicators.technical import indicators
from config import NIFTY_50_SYMBOLS, MIN_SCORE_TO_ALERT, MIN_RISK_REWARD


class SwingScanner:

    def scan_all(self):
        """
        Main function — scans all Nifty 50 stocks
        Returns list of valid swing opportunities
        """
        print("🔍 Starting Swing Scanner...")
        opportunities = []

        for symbol in NIFTY_50_SYMBOLS:
            try:
                result = self.analyze_stock(symbol)
                if result:
                    opportunities.append(result)
                    print(f"✅ {symbol} — Score: {result['score']}/10")
                else:
                    print(f"❌ {symbol} — No setup")
            except Exception as e:
                print(f"⚠️ {symbol} — Error: {e}")
                continue

        # Sort by score — highest first
        opportunities.sort(key=lambda x: x["score"], reverse=True)

        print(f"\n📊 Scan complete — {len(opportunities)} setups found")
        return opportunities

    def analyze_stock(self, symbol):
        """
        Analyze a single stock for swing setup
        Returns opportunity dict if valid, None if not
        """
        # Fetch daily candle data
        df = angel.get_historical_data(symbol, interval="ONE_DAY", days=100)
        if df is None or len(df) < 50:
            return None

        # Add all indicators
        df = indicators.add_all_indicators(df)

        # Run all checks
        trend = indicators.check_swing_trend(df)
        trend_strong = indicators.check_trend_strength(df)
        rsi_zone = indicators.check_rsi_zone(df)
        volume_confirmed = indicators.check_volume_confirmation(df)

        latest = df.iloc[-1]
        near_support = latest["near_support"]
        near_resistance = latest["near_resistance"]
        breakout = latest["breakout"]

        # Determine signal direction
        if trend == "BULLISH":
            signal = "BUY"
        elif trend == "BEARISH":
            signal = "SELL"
        else:
            return None  # No clear trend = skip

        # Reject if price near resistance on a BUY signal
        if signal == "BUY" and near_resistance and not breakout:
            return None

        # Calculate score
        score = self.calculate_score(
            trend=trend,
            trend_strong=trend_strong,
            rsi_zone=rsi_zone,
            volume_confirmed=volume_confirmed,
            near_support=near_support,
            breakout=breakout
        )

        # Reject if score below threshold
        if score < MIN_SCORE_TO_ALERT:
            return None

        # Calculate entry, SL, target
        trade_levels = indicators.calculate_sl_target(df, signal)
        if not trade_levels:
            return None

        # Reject if R/R below minimum
        if trade_levels["risk_reward"] < MIN_RISK_REWARD:
            return None

        # Estimate holding days based on ADX strength
        adx = latest["adx"]
        if adx >= 35:
            hold_days = "3-5 days"
        elif adx >= 25:
            hold_days = "5-7 days"
        else:
            hold_days = "7-10 days"

        return {
            "symbol": symbol,
            "signal": signal,
            "score": score,
            "entry": trade_levels["entry"],
            "stop_loss": trade_levels["stop_loss"],
            "target": trade_levels["target"],
            "risk_reward": trade_levels["risk_reward"],
            "hold_days": hold_days,
            "trend": trend,
            "rsi": round(latest["rsi"], 2),
            "adx": round(latest["adx"], 2),
            "volume_ratio": round(latest["volume_ratio"], 2),
            "near_support": near_support,
            "breakout": breakout,
            "rsi_zone": rsi_zone
        }

    def calculate_score(
            self, trend, trend_strong, rsi_zone,
            volume_confirmed, near_support, breakout
    ):
        """
        Score each stock out of 10
        Based on weighted conditions
        """
        score = 0

        # Trend direction — 20 points
        if trend in ["BULLISH", "BEARISH"]:
            score += 20

        # Trend strength (ADX) — 20 points
        if trend_strong:
            score += 20

        # RSI zone — 20 points
        if rsi_zone == "OVERSOLD":
            score += 20  # Best entry opportunity
        elif rsi_zone == "GOOD":
            score += 15  # Good entry
        elif rsi_zone == "NEUTRAL":
            score += 5  # Okay entry

        # Volume confirmation — 20 points
        if volume_confirmed:
            score += 20

        # Support/Resistance bonus — 20 points
        if breakout:
            score += 20  # Breakout = highest conviction
        elif near_support and trend == "BULLISH":
            score += 15  # Near support on bullish = good
        elif near_support:
            score += 10

        # Convert to 1-10 scale
        return round(score / 10, 1)

    def get_market_mood(self):
        """
        Check how many Nifty 50 stocks are above EMA 20
        Gives overall market direction
        """
        bullish_count = 0
        total_checked = 0

        for symbol in NIFTY_50_SYMBOLS:
            try:
                df = angel.get_historical_data(
                    symbol, interval="ONE_DAY", days=50
                )
                if df is None or len(df) < 20:
                    continue

                df = indicators.add_ema(df)
                latest = df.iloc[-1]

                if latest["close"] > latest["ema_20"]:
                    bullish_count += 1
                total_checked += 1

            except Exception:
                continue

        if total_checked == 0:
            return "UNKNOWN", 0, 0

        if bullish_count >= total_checked * 0.6:
            mood = "BULLISH 📈"
        elif bullish_count <= total_checked * 0.4:
            mood = "BEARISH 📉"
        else:
            mood = "NEUTRAL ➡️"

        return mood, bullish_count, total_checked


# Single instance
swing_scanner = SwingScanner()