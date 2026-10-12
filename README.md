# UK and Irish bookmaker prices: a sample snapshot

One snapshot of pre-match prices from UK and Irish bookmakers, taken from the [OddsRelay](https://oddsrelay.io)
odds API. It holds two views of the same moment:

- the **raw board**: each bookmaker's own markets, with outcomes named the way that bookmaker names them;
- the **standard matched board**: every bookmaker's price on the same outcome lined up under one name, with the line
  on line markets.

CSV and JSON, a data dictionary, a Frictionless `datapackage.json`, and [summary.md](summary.md): when the snapshot
was taken, how many events and prices it holds, and plain arithmetic on it, such as each bookmaker's margin on the
soccer result market.

## Files

| File | What it holds |
|---|---|
| `data/raw_prices.csv` | One row per raw-board price: event, bookmaker, market, outcome, price, and when that market last changed. |
| `data/matched_prices.csv` | One row per bookmaker price on the standard matched board: event, market, outcome, line, bookmaker, price. |
| `data/events.csv` | The events: sport, competition, start time, the two sides, and the racecourse for races. |
| `data/bookmakers.csv` | The bookmakers in the sample, by key and name. |
| `data/raw_board.json`, `data/standard_board.json` | The same prices in the API's own JSON shape, less what is left out below. |
| [DATA_DICTIONARY.md](DATA_DICTIONARY.md) | Every column with its type and meaning, and what each market key means. |
| [datapackage.json](datapackage.json) | The Frictionless Data descriptor: each table's schema and keys. |
| [snapshot.py](snapshot.py) | The script that took the snapshot and wrote every file above. |

The tables join on `event_id` and `bookmaker_key`.

## What it is not

- **Not the whole feed.** It is a sample: a few events per sport, a few markets per event.
- **Not a coverage figure.** Every count here (events, bookmakers, markets, prices), in `summary.md` and
  everywhere else, describes this one snapshot file. None of it measures what the OddsRelay feed covers.
- **Not a time series.** One snapshot, so no history, no closing prices and no results. Prices move all the time;
  these are the prices at one moment.
- **Not exchange data.** Bookmakers only: every exchange is left out, with every lay price and liquidity figure, and
  so is every venue under the Betfair name. Links to bookmakers' pages are left out too.
- **Not advice.** It is market data for building and analysis.

## Load it

With pandas, each bookmaker's margin on the soccer result market (1 / price summed over home, draw and away, minus 1):

```python
import pandas as pd

prices = pd.read_csv("data/raw_prices.csv")
events = pd.read_csv("data/events.csv")
books = pd.read_csv("data/bookmakers.csv")
prices = prices.merge(events[["event_id", "sport"]], on="event_id").merge(books, on="bookmaker_key")

result = prices[(prices["sport"] == "soccer") & (prices["market"] == "h2h")]
markets = (result.assign(inverse=1 / result["price"])
           .groupby(["event_id", "bookmaker_name"])
           .agg(outcomes=("price", "size"), inverse=("inverse", "sum")))
complete = markets[markets["outcomes"] == 3]
print((complete["inverse"] - 1).groupby("bookmaker_name").mean().round(3))
```

With the standard library only:

```python
import csv
from collections import Counter

with open("data/events.csv", newline="", encoding="utf-8") as f:
    events = {row["event_id"]: row for row in csv.DictReader(f)}
with open("data/raw_prices.csv", newline="", encoding="utf-8") as f:
    prices = list(csv.DictReader(f))

print(Counter(e["sport"] for e in events.values()).most_common())
print(Counter(p["market"] for p in prices).most_common())
```

Both are in [examples/](examples), and run from any folder.

## Rebuild it

```sh
export ODDSRELAY_KEY="your API key"
python3 snapshot.py --max-tokens <the most the run may spend>
```

Every data call is priced first with a free quote, and the run stops before it would spend more than
`--max-tokens`. It rewrites `data/`, `summary.md`, `DATA_DICTIONARY.md` and `datapackage.json`. Python 3.9 or later,
nothing to install. The key travels only in the `Authorization` header and is never written to a file.

## Current prices

This sample is one moment. For current prices, use the OddsRelay API:
[sign up](https://app.oddsrelay.io/signup) and copy your key from the dashboard. Free gives you 50,000 tokens for 14
days from sign-up, with no card, then no tokens until you choose a plan, on the same key.

- Docs: https://oddsrelay.io/docs
- API reference: https://oddsrelay.io/docs/reference
- Walking the raw board: https://oddsrelay.io/docs/guides/walking-raw

## Tests

```sh
python3 -m unittest -v
```

They check every file against `datapackage.json`, that no exchange price, link or key is in the repository, that the
JSON and CSV files agree, and that the examples run. No network, no key.

## Licence

The data (`data/`, `summary.md`, `DATA_DICTIONARY.md` and `datapackage.json`) is licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Attribution: OddsRelay (https://oddsrelay.io).
The code (`snapshot.py`, `examples/` and `tests/`) is under the MIT License. Both are in [LICENSE](LICENSE).
