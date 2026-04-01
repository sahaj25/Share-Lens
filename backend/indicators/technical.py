import pandas as pd
import ta

def calculate_indicators(df):
    """Calculate all technical indicators needed for swing scanner"""
    
    try:
        # EMA 20 and EMA 50
        df["ema20"] = ta.trend.ema_indicator(df["close"], window=20)
        df["ema50"] = ta.trend.ema_indicator(df["close"], window=50)
        
        # ADX — trend strength
        adx = ta.trend.ADXIndicator(df["high"], df["low"], df["close"], window=14)
        df["adx"] = adx.adx()
        
        # RSI
        df["rsi"] = ta.momentum.rsi(df["close"], window=14)
        
        # Volume 20-day average
        df["vol_avg_20"] = df["volume"].rolling(window=20).mean()
        
        # Volume ratio — today vs average
        df["vol_ratio"] = df["volume"] / df["vol_avg_20"]
        
        # Drop rows where indicators aren't ready yet
        df = df.dropna()
        
        return df
    
    except Exception as e:
        print(f"Indicator error: {e}")
        return None


def get_latest(df):
    """Return only the latest row — today's values"""
    return df.iloc[-1]


# Quick test
if __name__ == "__main__":
    # We'll import fetch function to test
    import sys
    sys.path.append(".")
    from data.angel_api import fetch_all_stocks
    
    print("Fetching data...")
    all_data = fetch_all_stocks()
    
    if all_data:
        print("\nCalculating indicators for all stocks...")
        
        results = {}
        for symbol, df in all_data.items():
            processed = calculate_indicators(df)
            if processed is not None:
                latest = get_latest(processed)
                results[symbol] = latest
                print(f"  ✓ {symbol} | EMA20: {latest['ema20']:.1f} | EMA50: {latest['ema50']:.1f} | ADX: {latest['adx']:.1f} | RSI: {latest['rsi']:.1f} | Vol Ratio: {latest['vol_ratio']:.2f}x")
        
        print(f"\nIndicators calculated for {len(results)} stocks")