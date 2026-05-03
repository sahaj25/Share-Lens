from angel_api import AngelAPI
from strategy import has_signal
from config import STOCKS
import time

def run():
    api = AngelAPI()
    results = []

    BATCH_SIZE = 50

    for i in range(0, len(STOCKS), BATCH_SIZE):
        batch = STOCKS[i:i + BATCH_SIZE]

        print(f"\nProcessing batch {i//BATCH_SIZE + 1}")

        for stock in batch:
            print("Checking:", stock["symbol"])

            df = api.get_data(stock["token"])
            time.sleep(0.3)

            if df.empty:
                continue

            result = has_signal(df)

            if result:
                results.append({
                    "symbol": stock["symbol"],
                    "price": result["price"],
                    "rsi": result["rsi"]
                })

        time.sleep(2)

    print("\n=== SIGNALS ===")

    if not results:
        print("No signals today")
    else:
        for r in results:
            print(f"{r['symbol']} | Price: {r['price']} | RSI: {r['rsi']}")

if __name__ == "__main__":
    run()