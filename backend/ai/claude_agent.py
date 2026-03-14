from google import genai
from config import GEMINI_API_KEY


class GeminiAgent:

    def __init__(self):
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.model = "gemini-2.5-flash"

    def _generate(self, prompt):
        """Core generation function"""
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt
        )
        return response.text

    def analyze_swing_signal(self, stock_data):
        """
        Takes swing scanner output
        Returns AI validated analysis + plain language explanation
        """
        prompt = f"""
You are an expert Indian stock market analyst specializing in technical analysis.
Analyze this swing trading signal for {stock_data['symbol']} and provide a structured assessment.

SIGNAL DATA:
- Symbol: {stock_data['symbol']}
- Signal: {stock_data['signal']}
- Score: {stock_data['score']}/10
- Entry: ₹{stock_data['entry']}
- Stop Loss: ₹{stock_data['stop_loss']}
- Target: ₹{stock_data['target']}
- Risk/Reward: 1:{stock_data['risk_reward']}
- Hold Period: {stock_data['hold_days']}
- Trend: {stock_data['trend']}
- RSI: {stock_data['rsi']} ({stock_data['rsi_zone']})
- ADX: {stock_data['adx']} (Trend Strength)
- Volume Ratio: {stock_data['volume_ratio']}x average
- Near Support: {stock_data['near_support']}
- Breakout: {stock_data['breakout']}

Respond in EXACTLY this format, nothing else:

CONFIDENCE: [HIGH/MEDIUM-HIGH/MEDIUM/LOW]
REASONING: [2-3 lines explaining why this is a good/bad setup in simple terms]
CAUTION: [Any red flags or risks to watch — 1 line, or write NONE]
ACTION: [Exact actionable instruction — buy at what level, what to watch]
"""
        try:
            text = self._generate(prompt)
            return self.parse_response(text, stock_data)
        except Exception as e:
            print(f"❌ Gemini API error: {e}")
            return self.fallback_analysis(stock_data)

    def analyze_intraday_signal(self, stock_data):
        """
        Takes intraday scanner output
        Returns AI validated analysis
        """
        prompt = f"""
You are an expert Indian stock market analyst specializing in intraday trading.
Analyze this intraday signal for {stock_data['symbol']}.

SIGNAL DATA:
- Symbol: {stock_data['symbol']}
- Signal: {stock_data['signal']}
- Score: {stock_data['score']}/10
- Time: {stock_data['time']}
- Entry: ₹{stock_data['entry']}
- Stop Loss: ₹{stock_data['stop_loss']}
- Target 1: ₹{stock_data['target_1']}
- Target 2: ₹{stock_data['target_2']}
- VWAP: ₹{stock_data['vwap']}
- EMA 9: ₹{stock_data['ema_9']}
- Volume Ratio: {stock_data['volume_ratio']}x average
- RSI: {stock_data['rsi']}

Respond in EXACTLY this format, nothing else:

CONFIDENCE: [HIGH/MEDIUM-HIGH/MEDIUM/LOW]
REASONING: [2 lines max — why this intraday setup is valid]
CAUTION: [Any risk to watch — 1 line, or write NONE]
ACTION: [Exact entry instruction — be specific]
"""
        try:
            text = self._generate(prompt)
            return self.parse_response(text, stock_data)
        except Exception as e:
            print(f"❌ Gemini API error: {e}")
            return self.fallback_intraday(stock_data)

    def analyze_market_mood(self, bullish_count, total, mood):
        """AI commentary on overall market mood"""
        prompt = f"""
You are an expert Indian stock market analyst.
Give a 2 line market outlook based on this data:

- Market Mood: {mood}
- Bullish stocks: {bullish_count} out of {total} Nifty 50 stocks above EMA 20

Be direct, practical, no fluff. 2 lines maximum.
"""
        try:
            text = self._generate(prompt)
            return text.strip()
        except Exception as e:
            print(f"❌ Gemini API error: {e}")
            return f"Market mood is {mood} with {bullish_count}/{total} stocks above EMA 20."

    def parse_response(self, text, stock_data):
        """Parse Gemini response into structured dict"""
        lines = text.strip().split("\n")
        result = {
            "symbol": stock_data["symbol"],
            "confidence": "MEDIUM",
            "reasoning": "",
            "caution": "NONE",
            "action": ""
        }
        for line in lines:
            line = line.strip()
            if line.startswith("CONFIDENCE:"):
                result["confidence"] = line.replace(
                    "CONFIDENCE:", ""
                ).strip()
            elif line.startswith("REASONING:"):
                result["reasoning"] = line.replace(
                    "REASONING:", ""
                ).strip()
            elif line.startswith("CAUTION:"):
                result["caution"] = line.replace(
                    "CAUTION:", ""
                ).strip()
            elif line.startswith("ACTION:"):
                result["action"] = line.replace(
                    "ACTION:", ""
                ).strip()
        return result

    def fallback_analysis(self, stock_data):
        """Used when Gemini API is unavailable"""
        confidence = "HIGH" if stock_data["score"] >= 8.5 else \
                     "MEDIUM-HIGH" if stock_data["score"] >= 7.5 else "MEDIUM"
        return {
            "symbol": stock_data["symbol"],
            "confidence": confidence,
            "reasoning": f"{stock_data['trend']} trend with ADX {stock_data['adx']} "
                        f"and RSI {stock_data['rsi']} in {stock_data['rsi_zone']} zone.",
            "caution": "NONE",
            "action": f"Enter at ₹{stock_data['entry']}, "
                     f"SL ₹{stock_data['stop_loss']}, "
                     f"Target ₹{stock_data['target']}"
        }

    def fallback_intraday(self, stock_data):
        """Fallback for intraday when Gemini API unavailable"""
        return {
            "symbol": stock_data["symbol"],
            "confidence": "MEDIUM",
            "reasoning": f"VWAP + EMA9 + Volume aligned for {stock_data['signal']} signal.",
            "caution": "NONE",
            "action": f"Enter at ₹{stock_data['entry']}, "
                     f"SL ₹{stock_data['stop_loss']}, "
                     f"Target ₹{stock_data['target_2']}"
        }


# Single instance
claude_agent = GeminiAgent()