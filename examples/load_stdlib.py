"""Load the sample with the standard library only: events per sport, prices per market, and one soccer event's
result-market prices on the matched board.

Run: python3 examples/load_stdlib.py
"""
import csv
from collections import Counter, defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def read(table):
    with open(DATA / f"{table}.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


events = {e["event_id"]: e for e in read("events")}
raw = read("raw_prices")
matched = read("matched_prices")
print("events per sport:", Counter(e["sport"] for e in events.values()).most_common())
print("raw prices per market:", Counter(p["market"] for p in raw).most_common())

soccer = [p for p in matched if p["market"] == "h2h" and events[p["event_id"]]["sport"] == "soccer"]
if soccer:
    event = events[soccer[0]["event_id"]]
    by_outcome = defaultdict(list)
    for p in soccer:
        if p["event_id"] == event["event_id"]:
            by_outcome[p["outcome"]].append(float(p["price"]))
    print(f"{event['home_team']} v {event['away_team']}, {event['competition']}, {event['commence_time']}")
    for outcome, prices in by_outcome.items():
        print(f"  {outcome}: {len(prices)} bookmakers, prices {min(prices)} to {max(prices)}")
