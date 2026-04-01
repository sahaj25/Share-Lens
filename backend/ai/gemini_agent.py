import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def validate_signal(signal):
    """
    Send signal to Gemini for validation and plain English explanation.
    Returns enriched signal with ai_verdict, ai_reason, ai_caution
    """

    prompt = f"""
You are a stock trading signal validator for Indian markets (NSE/Nifty 50).

A technical scanner has generated this swing trade signal. Validate it and respond.

SIGNAL DATA:
- Stock: {signal['symbol']}
- Trend: {signal['trend']}
- Entry: ₹{signal['entry']}
- Stop Loss: ₹{signal['sl']} ({signal['sl_pct']}% risk)
- Target: ₹{signal['target']} ({signal['target_pct']}% gain)
- R/R Ratio: 1:{signal['rr']}
- RSI: {signal['rsi']}
- ADX: {signal['adx']}
- Volume Ratio: {signal['vol_ratio']}x average
- Hold Duration: {signal['hold_days']}
- Technical Reasons: {' + '.join(signal['reasons'])}
- Score: {signal['score']}/10

Respond in this EXACT format, nothing else:

VERDICT: VALID or WEAK
REASON: (1-2 sentences explaining why this is a good or weak setup in plain English)
CAUTION: (1 sentence — any risk or thing to watch out for, or write NONE if no caution)
CONFIDENCE: (a number 1-10)
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        text = response.text.strip()

        lines = text.split("\n")
        parsed = {}
        for line in lines:
            if line.startswith("VERDICT:"):
                parsed["ai_verdict"] = line.replace("VERDICT:", "").strip()
            elif line.startswith("REASON:"):
                parsed["ai_reason"] = line.replace("REASON:", "").strip()
            elif line.startswith("CAUTION:"):
                parsed["ai_caution"] = line.replace("CAUTION:", "").strip()
            elif line.startswith("CONFIDENCE:"):
                try:
                    parsed["ai_confidence"] = float(line.replace("CONFIDENCE:", "").strip())
                except:
                    parsed["ai_confidence"] = signal["score"]

        if "ai_verdict" not in parsed:
            parsed["ai_verdict"] = "VALID"
        if "ai_reason" not in parsed:
            parsed["ai_reason"] = "Technical setup looks clean."
        if "ai_caution" not in parsed:
            parsed["ai_caution"] = "NONE"
        if "ai_confidence" not in parsed:
            parsed["ai_confidence"] = signal["score"]

        signal.update(parsed)
        return signal

    except Exception as e:
        print(f"Gemini error for {signal['symbol']}: {e}")
        signal["ai_verdict"] = "VALID"
        signal["ai_reason"] = "AI validation unavailable."
        signal["ai_caution"] = "Could not validate with AI."
        signal["ai_confidence"] = signal["score"]
        return signal


def filter_by_ai(signals):
    """Run all signals through Gemini, remove WEAK ones"""
    validated = []

    for signal in signals:
        print(f"  Validating {signal['symbol']} with Gemini...")
        result = validate_signal(signal)

        if result["ai_verdict"] == "VALID":
            validated.append(result)
            print(f"  ✅ {result['symbol']} — {result['ai_verdict']} | Confidence: {result['ai_confidence']}/10")
        else:
            print(f"  ❌ {result['symbol']} — rejected by AI ({result['ai_reason']})")

    return validated


# Quick test
if __name__ == "__main__":
    test_signal = {
        "symbol": "ONGC",
        "score": 7.5,
        "entry": 284.6,
        "sl": 274.2,
        "target": 305.6,
        "sl_pct": 3.7,
        "target_pct": 7.4,
        "rr": 2.0,
        "rsi": 65.3,
        "adx": 32.2,
        "vol_ratio": 1.51,
        "trend": "bullish",
        "reasons": ["EMA20 > EMA50", "ADX 32.2", "Volume 1.5x", "no key level nearby"],
        "close": 284.6,
        "hold_days": "5-8 days",
        "qty": 35,
        "capital_needed": 9961.0,
        "max_loss": 364.0,
        "max_profit": 735.0,
        "score_breakdown": {"trend": 20, "adx": 15, "rsi": 10, "volume": 15, "rr": 15},
        "raw_score": 75,
    }

    print("Sending to Gemini for validation...\n")
    result = validate_signal(test_signal)

    print(f"Verdict: {result['ai_verdict']}")
    print(f"Reason: {result['ai_reason']}")
    print(f"Caution: {result['ai_caution']}")
    print(f"Confidence: {result['ai_confidence']}/10")