---
license: cc-by-4.0
pretty_name: UK and Irish bookmaker prices (sample snapshot)
language:
- en
tags:
- sports
- odds
- bookmakers
- football
- tennis
- horse-racing
- tabular
size_categories:
- 10K<n<100K
configs:
- config_name: raw_prices
  data_files: data/raw_prices.csv
  default: true
- config_name: matched_prices
  data_files: data/matched_prices.csv
- config_name: events
  data_files: data/events.csv
- config_name: bookmakers
  data_files: data/bookmakers.csv
---

# UK and Irish bookmaker prices: a sample snapshot

One snapshot of pre-match prices from UK and Irish bookmakers, taken from the [OddsRelay](https://oddsrelay.io)
odds API, across the sports it carries. Two views of the same moment:

- **`raw_prices`**: the raw board, one row per price: each bookmaker's own markets, with outcomes named the way that
  bookmaker names them.
- **`matched_prices`**: the standard matched board, one row per bookmaker price, with every bookmaker's price on the
  same outcome under one name and the line (`point`) on line markets.
- **`events`** and **`bookmakers`**: the events (sport, competition, start time, sides, racecourse) and the
  bookmakers' names. Every table joins on `event_id` and `bookmaker_key`.

The same prices are in `data/raw_board.json` and `data/standard_board.json` in the API's own JSON shape.
`summary.md` says when the snapshot was taken, how many events and prices it holds, and gives plain arithmetic on
it, such as each bookmaker's margin on the soccer result market. `DATA_DICTIONARY.md` gives every column's type and
meaning.

## Load it

```python
from datasets import load_dataset

prices = load_dataset("oddsrelay/uk-bookmaker-prices-sample", "raw_prices", split="train")
events = load_dataset("oddsrelay/uk-bookmaker-prices-sample", "events", split="train")
```

Or with pandas, from a copy of the files:

```python
import pandas as pd

prices = pd.read_csv("data/raw_prices.csv").merge(pd.read_csv("data/events.csv"), on="event_id")
```

## What it is not

- **Not the whole feed.** It is a sample: a few events per sport, a few markets per event.
- **Not a time series.** One snapshot, so no history, no closing prices and no results.
- **Not exchange data.** Bookmakers only: every exchange is left out, with every lay price and liquidity figure, and
  so is every venue under the Betfair name. Links to bookmakers' pages are left out too.
- **Not advice.** It is market data for building and analysis.

## How it was made

`snapshot.py` in the [GitHub repository](https://github.com/oddsrelay/sample-data) read the API's raw board and
standard matched board once each, for events scheduled to start in the following 24 hours, kept bookmaker prices
only, picked a few events per sport (those on the matched board first, then those with the most bookmakers) and wrote
these files. It can be run again with an API key to take a new snapshot.

## Current prices

For current prices on every event and market the API carries, use the OddsRelay API:
[sign up](https://app.oddsrelay.io/signup) and copy your key from the dashboard. Free gives you 50,000 tokens for 14
days from sign-up, with no card, then no tokens until you choose a plan, on the same key.
Docs: https://oddsrelay.io/docs

## Licence

CC BY 4.0. Attribution: OddsRelay (https://oddsrelay.io).
