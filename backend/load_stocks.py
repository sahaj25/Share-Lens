import requests

def get_nifty200_stocks():
    # Load Nifty 200 symbols
    url_csv = "https://archives.nseindia.com/content/indices/ind_nifty200list.csv"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url_csv, headers=headers)

    lines = res.text.split("\n")[1:]

    nifty_symbols = set()
    for line in lines:
        if line.strip():
            parts = line.split(",")
            symbol = parts[2].strip()
            nifty_symbols.add(symbol)

    # Load Angel master
    url_json = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
    data = requests.get(url_json).json()

    stocks = []

    for item in data:
        if (
            item["exch_seg"] == "NSE" and
            item["symbol"].endswith("-EQ")
        ):
            symbol = item["symbol"].replace("-EQ", "")

            if symbol in nifty_symbols:
                stocks.append({
                    "symbol": symbol,
                    "token": item["token"]
                })

    return stocks