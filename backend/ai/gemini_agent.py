from google import genai
from config import GEMINI_API_KEY


# Valid confidence levels the model should return
VALID_CONFIDENCE = {"HIGH", "MEDIUM-HIGH", "MEDIUM", "LOW"}


class GeminiAgent:

    def __init__(self):
        # FIX: wrapped in try/except — if GEMINI_API_KEY is missing or
        # invalid, the original would crash at import time with a cryptic
        # error. Now fails clearly with a useful message.
        try:
            self.client = genai.Client(api_key=GEMINI_API_KEY)
        except Exception as e:
            print(f"❌ Gemini client init failed: {e}")
            self.client = None

        self.model = "gemini-2.5-flash"

    def _generate(self, prompt):
        """Core generation function"""
        # FIX: guard against uninitialised client (e.g. bad API key at boot)
        if not self.client:
            raise RuntimeError("Gemini client is not initialised — check GEMINI_API_KEY")

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt
        )

        # FIX: response.text can be None if Gemini returns an empty or
        # safety-blocked response — previously this would crash downstream
        # with an AttributeError on None
        if not response.text:
            raise ValueError("Gemini returned an empty response")

        return response.text

    def analyze_swing_signal(self, stock_data):
        """
        Takes swing scanner output.
        Returns AI validated analysis + plain language explanation.
        """
        # FIX: validate required keys exist before building the prompt.
        # A missing key would crash with a confusing KeyError mid-prompt.
        required = [
            "symbol", "signal", "score", "entry", "stop_loss",
            "target", "risk_reward", "hold_days", "trend",
            "rsi", "rsi_zone", "adx", "volume_ratio",
            "near_support", "breakout"
        ]
        for key in required:
            if key not in stock_data:
                print(f"⚠️ Missing key '{key}' in stock_data — using fallback")
                return self.fallback_analysis(stock_data)

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
            print(f"❌ Gemini API error (swing): {e}")
            return self.fallback_analysis(stock_data)

    def analyze_intraday_signal(self, stock_data):
        """
        Takes intraday scanner output.
        Returns AI validated analysis.
        """
        required = [
            "symbol", "signal", "score", "time", "entry",
            "stop_loss", "target_1", "target_2",
            "vwap", "ema_9", "volume_ratio", "rsi"
        ]
        for key in required:
            if key not in stock_data:
                print(f"⚠️ Missing key '{key}' in stock_data — using fallback")
                return self.fallback_intraday(stock_data)

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
            print(f"❌ Gemini API error (intraday): {e}")
            return self.fallback_intraday(stock_data)

    def analyze_market_mood(self, bullish_count, total, mood):
        """AI commentary on overall market mood"""
        # FIX: guard against division-by-zero if total = 0
        if total == 0:
            return f"Market data unavailable — no stocks scanned."

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
            print(f"❌ Gemini API error (market mood): {e}")
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
                value = line.replace("CONFIDENCE:", "").strip()
                # FIX: validate confidence value — if Gemini hallucinates
                # something unexpected (e.g. "VERY HIGH"), fall back to MEDIUM
                # so downstream emoji logic in telegram_bot.py doesn't break
                result["confidence"] = value if value in VALID_CONFIDENCE else "MEDIUM"

            elif line.startswith("REASONING:"):
                result["reasoning"] = line.replace("REASONING:", "").strip()

            elif line.startswith("CAUTION:"):
                result["caution"] = line.replace("CAUTION:", "").strip()

            elif line.startswith("ACTION:"):
                result["action"] = line.replace("ACTION:", "").strip()

        # FIX: if Gemini ignored the format entirely and none of the fields
        # were parsed, return the fallback instead of an empty result dict
        if not result["reasoning"] and not result["action"]:
            print(f"⚠️ Gemini response unparseable for {stock_data['symbol']} — using fallback")
            # Determine which fallback to use based on available keys
            if "hold_days" in stock_data:
                return self.fallback_analysis(stock_data)
            return self.fallback_intraday(stock_data)

        return result

    def fallback_analysis(self, stock_data):
        """Used when Gemini API is unavailable — swing trades"""
        score = stock_data.get("score", 0)
        confidence = (
            "HIGH"        if score >= 8.5 else
            "MEDIUM-HIGH" if score >= 7.5 else
            "MEDIUM"
        )
        return {
            "symbol": stock_data.get("symbol", "UNKNOWN"),
            "confidence": confidence,
            # FIX: used .get() with defaults so fallback never crashes
            # even if stock_data is partially populated
            "reasoning": (
                f"{stock_data.get('trend', 'N/A')} trend with "
                f"ADX {stock_data.get('adx', 'N/A')} and "
                f"RSI {stock_data.get('rsi', 'N/A')} in "
                f"{stock_data.get('rsi_zone', 'N/A')} zone."
            ),
            "caution": "NONE",
            "action": (
                f"Enter at ₹{stock_data.get('entry', 'N/A')}, "
                f"SL ₹{stock_data.get('stop_loss', 'N/A')}, "
                f"Target ₹{stock_data.get('target', 'N/A')}"
            )
        }

    def fallback_intraday(self, stock_data):
        """Fallback for intraday when Gemini API is unavailable"""
        return {
            "symbol": stock_data.get("symbol", "UNKNOWN"),
            "confidence": "MEDIUM",
            # FIX: used .get() with defaults — same reason as above
            "reasoning": (
                f"VWAP + EMA9 + Volume aligned for "
                f"{stock_data.get('signal', 'N/A')} signal."
            ),
            "caution": "NONE",
            "action": (
                f"Enter at ₹{stock_data.get('entry', 'N/A')}, "
                f"SL ₹{stock_data.get('stop_loss', 'N/A')}, "
                f"Target ₹{stock_data.get('target_2', 'N/A')}"
            )
        }


# FIX: renamed from claude_agent to gemini_agent — matches the class name
# and avoids confusion when imported in jobs.py
gemini_agent = GeminiAgent()