from alerts.telegram_bot import telegram_bot

# Test 1 — Basic message
print("Testing Telegram...")
telegram_bot.send_message("✅ Trading Tool test message — Telegram is working!")

# Test 2 — Health check format
telegram_bot.send_health_check()

print("Done — check your Telegram!")

from database.models import create_tables
from database.queries import db_queries

print("Testing Database...")
create_tables()
print("✅ Database tables created successfully")


import pandas as pd
import numpy as np
from indicators.technical import indicators

print("Testing Indicators...")

# Create dummy OHLCV data
dates = pd.date_range("2026-01-01", periods=100, freq="D")
df = pd.DataFrame({
    "open": np.random.uniform(100, 200, 100),
    "high": np.random.uniform(150, 250, 100),
    "low": np.random.uniform(80, 150, 100),
    "close": np.random.uniform(100, 200, 100),
    "volume": np.random.uniform(1000000, 5000000, 100)
}, index=dates)

df = indicators.add_all_indicators(df)
print(f"✅ Indicators working — columns: {list(df.columns)}")

trend = indicators.check_swing_trend(df)
strength = indicators.check_trend_strength(df)
rsi_zone = indicators.check_rsi_zone(df)

print(f"✅ Trend: {trend}")
print(f"✅ Strong trend: {strength}")
print(f"✅ RSI zone: {rsi_zone}")

trade = indicators.calculate_sl_target(df, "BUY")
if trade:
    print(
        f"✅ Entry: {trade['entry']} | SL: {trade['stop_loss']} | Target: {trade['target']} | R/R: 1:{trade['risk_reward']}")
else:
    print("⚠️ calculate_sl_target returned None — checking...")
    latest = df.iloc[-1]
    print(f"Support: {latest['support']} | Close: {latest['close']}")

print("\n🧪 TEST 4 — Gemini AI")
from ai.claude_agent import claude_agent

test_signal = {
    "symbol": "HDFCBANK",
    "signal": "BUY",
    "score": 8.5,
    "entry": 1685.0,
    "stop_loss": 1648.0,
    "target": 1760.0,
    "risk_reward": 2.1,
    "hold_days": "4-6 days",
    "trend": "BULLISH",
    "rsi": 45.2,
    "rsi_zone": "GOOD",
    "adx": 28.5,
    "volume_ratio": 1.8,
    "near_support": True,
    "breakout": False
}

result = claude_agent.analyze_swing_signal(test_signal)
print(f"✅ Confidence: {result['confidence']}")
print(f"✅ Reasoning: {result['reasoning']}")
print(f"✅ Caution: {result['caution']}")
print(f"✅ Action: {result['action']}")
