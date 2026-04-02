import pandas as pd
import sys
sys.path.append(".")
from data.nifty200_symbols import NIFTY200_SYMBOLS


def load_master():
    """Load the Angel One master CSV"""
    try:
        df = pd.read_csv("storage/angel_master.csv")
        return df
    except Exception as e:
        print(f"Error loading master file: {e}")
        return None


def resolve_tokens():
    """
    Match Nifty 200 symbols against Angel One master file
    Returns dict of {symbol: token}
    """
    master = load_master()
    if master is None:
        return None

    # Build lookup dict from master
    token_map = dict(zip(master["clean_symbol"], master["token"].astype(str)))

    resolved = {}
    failed = []

    for symbol in NIFTY200_SYMBOLS:
        if symbol in token_map:
            resolved[symbol] = token_map[symbol]
        else:
            failed.append(symbol)

    print(f"Resolved: {len(resolved)}/{len(NIFTY200_SYMBOLS)} symbols")
    if failed:
        print(f"Failed to resolve: {failed}")

    return resolved


if __name__ == "__main__":
    tokens = resolve_tokens()
    if tokens:
        print("\nSample tokens:")
        for sym, tok in list(tokens.items())[:10]:
            print(f"  {sym}: {tok}")