"""Load the sample with pandas: each bookmaker's mean margin on the soccer result market.

Run: python3 examples/load_pandas.py   (needs pandas)
"""
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"

prices = pd.read_csv(DATA / "raw_prices.csv", parse_dates=["last_update"])
events = pd.read_csv(DATA / "events.csv", parse_dates=["commence_time"])
books = pd.read_csv(DATA / "bookmakers.csv")
prices = prices.merge(events[["event_id", "sport"]], on="event_id").merge(books, on="bookmaker_key")

# One bookmaker's market on one event is complete when it prices home, draw and away.
result = prices[(prices["sport"] == "soccer") & (prices["market"] == "h2h")]
markets = (result.assign(inverse=1 / result["price"])
           .groupby(["event_id", "bookmaker_name"])
           .agg(outcomes=("price", "size"), inverse=("inverse", "sum")))
complete = markets[markets["outcomes"] == 3]
margin = (complete["inverse"] - 1).groupby("bookmaker_name").agg(["size", "mean"])
print(margin.rename(columns={"size": "markets", "mean": "mean_margin"}).round(3).to_string())
