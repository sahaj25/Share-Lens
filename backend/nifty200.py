import requests

def get_nifty200_symbols():
    url = "https://archives.nseindia.com/content/indices/ind_nifty200list.csv"
    headers = {"User-Agent": "Mozilla/5.0"}

    res = requests.get(url, headers=headers)

    lines = res.text.split("\n")[1:]  # skip header

    symbols = []
    for line in lines:
        if line.strip():
            parts = line.split(",")
            symbol = parts[2].strip()
            symbols.append(symbol)

    return symbols