#!/usr/bin/env python3
"""Rebuild this sample: one snapshot of UK and Irish bookmaker prices from the OddsRelay API.

    ODDSRELAY_KEY=<your key> python3 snapshot.py --max-tokens <n>

It reads the raw board and the standard matched board once each, keeps bookmakers only (every exchange venue, lay
price, liquidity figure and link is left out), picks a few events per sport, and rewrites data/, summary.md,
DATA_DICTIONARY.md and datapackage.json. Every data call is priced first with a free quote, and the run stops before
it would spend more than --max-tokens. Standard library only, Python 3.9 or later.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import json
import os
import statistics
import sys
import time
from collections import Counter, defaultdict
from typing import Any, Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = "https://api.oddsrelay.io"
REGION = "uk"  # the UK and Ireland
HOURS = 24  # events scheduled to start in the 24 hours after the snapshot
PER_SPORT = 15  # events kept per sport: those on the matched board first, then the most bookmakers
RAW_MARKETS = "h2h,btts,outright_winner"
STANDARD_MARKETS = "h2h,totals,btts,win"
LEFT_OUT = ("betfair",)  # venues whose key holds one of these are left out, on top of every exchange
ATTRIBUTION = "OddsRelay (https://oddsrelay.io)"
HERE = os.path.dirname(os.path.abspath(__file__))

# Every column of every table: (name, type, meaning). Frictionless types; the docs and metadata are built from this.
TABLES: dict[str, tuple[str, list[str], list[tuple[str, str, str]]]] = {
    "bookmakers": ("One row per bookmaker with at least one price in this sample.", ["bookmaker_key"], [
        ("bookmaker_key", "string", "Short identifier of the bookmaker, the same one the API uses. Joins to the "
                                    "price tables."),
        ("bookmaker_name", "string", "The bookmaker's name as it is displayed."),
    ]),
    "events": ("One row per event in this sample. On the raw board one fixture can appear as two events when "
               "bookmakers name or time it differently: compare sides and start times before counting fixtures.",
               ["event_id"], [
        ("event_id", "string", "Identifier of the event in the API. Use it to join these files; it is not meant "
                               "as a permanent key."),
        ("sport", "string", "The sport, for example soccer, tennis or horse_racing."),
        ("sport_key", "string", "The competition's identifier, which starts with the sport."),
        ("competition", "string", "The competition's name, or the sport's name where there is no competition."),
        ("commence_time", "datetime", "Scheduled start, in UTC."),
        ("home_team", "string", "The home side, or the first-named player. Empty for events without sides, such "
                                "as races."),
        ("away_team", "string", "The away side, or the second-named player. Empty for events without sides."),
        ("event_name", "string", "The event's name where it does not split into two sides. Often empty."),
        ("course", "string", "Racing only: the racecourse, where the matched board names it. Otherwise empty."),
    ]),
    "raw_prices": ("One row per price on the raw board: one bookmaker, one event, one market, one outcome. "
                   "Outcome names are each bookmaker's own.", [], [
        ("event_id", "string", "The event (events.csv)."),
        ("bookmaker_key", "string", "The bookmaker (bookmakers.csv)."),
        ("market", "string", "The market's key (DATA_DICTIONARY.md says what each one means)."),
        ("outcome", "string", "The selection, worded as this bookmaker words it."),
        ("price", "number", "Decimal price: what one unit staked returns if the outcome wins, stake included."),
        ("last_update", "datetime", "When this bookmaker's prices on this market last changed, in UTC."),
    ]),
    "matched_prices": ("One row per bookmaker price on the standard matched board, where every bookmaker's "
                       "offer on the same outcome sits under one outcome name. Exchange prices are left out.", [], [
        ("event_id", "string", "The event (events.csv)."),
        ("market", "string", "The market's key (DATA_DICTIONARY.md says what each one means)."),
        ("outcome", "string", "The selection, named once for every bookmaker."),
        ("point", "number", "The line on a line market, for example 2.5 on totals. Empty on other markets."),
        ("bookmaker_key", "string", "The bookmaker (bookmakers.csv)."),
        ("price", "number", "Decimal price, as in raw_prices.csv."),
    ]),
}
REQUIRED = {"event_id", "bookmaker_key", "bookmaker_name", "sport", "sport_key", "market", "outcome", "price"}
FOREIGN = {"raw_prices": ["event_id", "bookmaker_key"], "matched_prices": ["event_id", "bookmaker_key"]}
MARKETS = {
    "h2h": "The result. Two outcomes (one side or the other) or three where a draw is possible (home, draw, away).",
    "btts": "Both teams to score: yes or no.",
    "totals": "The total goals or points, over or under the line in point.",
    "outright_winner": "The winner of a race or field: one outcome per runner.",
    "win": "Racing: the winner of the race, one outcome per runner.",
}


# ---- the API --------------------------------------------------------------------------------------------------------

def get(path: str, params: dict) -> tuple[Any, Any]:
    """GET one route with gzip: (headers, decoded JSON). Waits out 429s, exits on any other error."""
    key = (os.environ.get("ODDSRELAY_KEY") or os.environ.get("OR_KEY") or "").strip()
    if not key:
        sys.exit("set ODDSRELAY_KEY to your API key")
    query = urlencode({k: v for k, v in params.items() if v is not None})
    for attempt in range(3):
        req = Request(f"{API}{path}" + (f"?{query}" if query else ""),
                      headers={"Authorization": f"Bearer {key}", "Accept-Encoding": "gzip"})
        try:
            with urlopen(req, timeout=60) as res:
                status, hdrs, body = res.status, res.headers, res.read()
        except HTTPError as err:
            status, hdrs, body = err.code, err.headers, err.read()
        except URLError as err:
            sys.exit(f"could not reach {API}: {err.reason}")
        if body and hdrs.get("Content-Encoding") == "gzip":
            body = gzip.decompress(body)
        if status == 429:
            if attempt < 2:
                time.sleep(int(hdrs.get("Retry-After") or "1"))
            continue
        if status >= 400:
            error = json.loads(body).get("error", {}) if body[:1] == b"{" else {}
            sys.exit(f"HTTP {status} {error.get('code', '')}: {error.get('message', '')} "
                     f"(request id {error.get('request_id', '-')})")
        return hdrs, json.loads(body)
    sys.exit("still rate-limited after 3 tries")


class Meter:
    """Prices each data call with a free quote first and refuses any call that would pass the ceiling."""

    def __init__(self, ceiling: int):
        self.ceiling, self.spent = ceiling, 0

    def __call__(self, path: str, params: dict) -> Any:
        cost = get(path, {**params, "quote": "true"})[1]["cost"]
        if self.spent + cost > self.ceiling:
            sys.exit(f"stopped: the next call is priced at {cost} tokens, {self.spent} are spent and "
                     f"--max-tokens is {self.ceiling}")
        hdrs, body = get(path, params)
        self.spent += int(hdrs.get("X-Tokens-Cost") or cost)
        return body


# ---- keeping bookmakers only ----------------------------------------------------------------------------------------

def iso(value: Any) -> Any:
    """An API time to ISO-8601 UTC whole seconds (2026-10-11T20:03:45Z); anything else unchanged."""
    if isinstance(value, str) and value.endswith("Z") and "T" in value:
        return value[:19] + "Z"
    return value


def is_price(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def strip_raw(event: dict, books: set) -> dict:
    """A raw-board event with only the given bookmakers' plain prices: no exchange venue, no lay market or field."""
    venues = []
    for venue in event.get("bookmakers") or []:
        if venue.get("key") not in books:
            continue
        markets = []
        for market in venue.get("markets") or []:
            if market["key"].endswith("_lay"):
                continue
            outcomes = [{"name": o["name"], "price": o["price"]} for o in market.get("outcomes") or []
                        if set(o) <= {"name", "price"} and is_price(o.get("price"))]
            if outcomes:
                markets.append({"key": market["key"], "last_update": iso(market.get("last_update")),
                                "outcomes": outcomes})
        if markets:
            venues.append({"key": venue["key"], "title": venue["title"],
                           "last_update": iso(venue.get("last_update")), "markets": markets})
    keep = ("id", "sport_key", "sport_title", "commence_time", "home_team", "away_team")
    return {**{k: iso(event.get(k)) for k in keep}, "bookmakers": venues}


def strip_matched(event: dict, books: set) -> dict:
    """A matched-board event with the given bookmakers' back prices only: no lay side, no exchange, no link."""
    markets = []
    for market in event.get("markets") or []:
        outcomes = []
        for o in market.get("outcomes") or []:
            back = [{"bookmaker": b["bookmaker"], "price": b["price"]} for b in o.get("back") or []
                    if b.get("bookmaker") in books and is_price(b.get("price"))]
            if back:
                outcomes.append({"name": o["name"], **({"point": o["point"]} if "point" in o else {}), "back": back})
        if outcomes:
            markets.append({"key": market["key"], "outcomes": outcomes})
    keep = ("event_id", "sport_key", "sport_title", "commence_time", "home_team", "away_team", "event_name", "venue")
    return {**{k: iso(event[k]) for k in keep if k in event}, "markets": markets}


def sport_of(sport_key: str, sports: Iterable[str]) -> str:
    """The sport a competition key sits under: the longest sport that is the key or starts it."""
    hits = [s for s in sports if sport_key == s or sport_key.startswith(s + "_")]
    return max(hits, key=len) if hits else sport_key.split("_")[0]


def pick(raw: list[dict], on_matched: set, sport: Callable[[str], str], per_sport: int) -> list[dict]:
    """Up to per_sport events per sport with two or more bookmakers: those on the matched board first, then the most
    bookmakers, then the earliest start. Returned in start order."""
    by_sport = defaultdict(list)
    for event in raw:
        if len(event["bookmakers"]) >= 2:
            by_sport[sport(event["sport_key"])].append(event)
    kept = []
    for events in by_sport.values():
        events.sort(key=lambda e: (e["id"] not in on_matched, -len(e["bookmakers"]), str(e["commence_time"]), e["id"]))
        kept += events[:per_sport]
    return sorted(kept, key=lambda e: (str(e["commence_time"]), e["id"]))


# ---- tables ---------------------------------------------------------------------------------------------------------

def raw_rows(events: list[dict]) -> Iterable[dict]:
    for e in events:
        for v in e["bookmakers"]:
            for m in v["markets"]:
                for o in m["outcomes"]:
                    yield {"event_id": e["id"], "bookmaker_key": v["key"], "market": m["key"], "outcome": o["name"],
                           "price": o["price"], "last_update": m["last_update"]}


def matched_rows(events: list[dict]) -> Iterable[dict]:
    for e in events:
        for m in e["markets"]:
            for o in m["outcomes"]:
                for b in o["back"]:
                    yield {"event_id": e["event_id"], "market": m["key"], "outcome": o["name"],
                           "point": o.get("point"), "bookmaker_key": b["bookmaker"], "price": b["price"]}


def event_rows(raw: list[dict], matched: dict, sport: Callable[[str], str]) -> list[dict]:
    rows = []
    for e in raw:
        m = matched.get(e["id"], {})
        rows.append({"event_id": e["id"], "sport": sport(e["sport_key"]), "sport_key": e["sport_key"],
                     "competition": e["sport_title"], "commence_time": e["commence_time"],
                     "home_team": e["home_team"], "away_team": e["away_team"],
                     "event_name": m.get("event_name"), "course": m.get("venue")})
    return rows


def write_csv(path: str, table: str, rows: Iterable[dict]) -> int:
    names = [f[0] for f in TABLES[table][2]]
    count = 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=names, lineterminator="\n")
        writer.writeheader()
        for count, row in enumerate(rows, 1):
            writer.writerow(row)
    return count


def write_json(path: str, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")


# ---- the summary ----------------------------------------------------------------------------------------------------

def overround(prices: list[float]) -> float:
    """A market's margin: the sum of 1/price over every outcome, minus 1 (0.05 is 5%)."""
    return sum(1 / p for p in prices) - 1


def result_margins(rows: list[dict], sport_by_event: dict) -> list[tuple[str, str, str, float]]:
    """(sport, event, bookmaker, margin) for every complete result (h2h) market: one bookmaker, one event, as many
    outcomes as that sport's result markets most often have, every price above 1."""
    books = defaultdict(list)
    for r in rows:
        if r["market"] == "h2h":
            books[(r["event_id"], r["bookmaker_key"])].append(r["price"])
    size = defaultdict(Counter)
    for (event, _), prices in books.items():
        size[sport_by_event[event]][len(prices)] += 1
    usual = {s: c.most_common(1)[0][0] for s, c in size.items()}
    return [(sport_by_event[e], e, b, overround(p)) for (e, b), p in books.items()
            if len(p) == usual[sport_by_event[e]] and len(p) >= 2 and all(x > 1 for x in p)]


def every_event_margins(margins: list[tuple[str, str, str, float]], sport: str) -> tuple[int, dict]:
    """(n, {bookmaker: margins}) on one sport's result market, n being the events with a complete market from anyone,
    for the bookmakers with a complete market on all n: a consistent sample, so every mean averages the same events."""
    by_book, events = defaultdict(list), set()
    for s, event, book, m in margins:
        if s == sport:
            by_book[book].append(m)
            events.add(event)
    return len(events), {b: ms for b, ms in by_book.items() if len(ms) == len(events)}


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def when(stamp: str) -> str:
    t = dt.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")
    return f"{t.day} {t:%B %Y} at {t:%H:%M} UTC"


def summary(s: dict) -> str:
    events, raw, matched, names = s["events"], s["raw_rows"], s["matched_rows"], s["names"]
    sport_by_event = {e["event_id"]: e["sport"] for e in events}
    books_per_event = defaultdict(set)
    for r in raw:
        books_per_event[r["event_id"]].add(r["bookmaker_key"])
    sample = defaultdict(list)
    for e in events:
        sample[e["sport"]].append(len(books_per_event[e["event_id"]]))
    margins = result_margins(raw, sport_by_event)
    by_sport = defaultdict(list)
    for sport, _, _, m in margins:
        by_sport[sport].append(m)
    soccer_events, by_book = every_event_margins(margins, "soccer")
    spread = defaultdict(list)
    outcome_prices = defaultdict(list)
    for r in matched:
        if r["market"] == "h2h":
            outcome_prices[(r["event_id"], r["outcome"], r["point"])].append(r["price"])
    for (event, _, _), prices in outcome_prices.items():
        if len(prices) >= 2 and min(prices) > 0:
            spread[sport_by_event[event]].append(max(prices) / min(prices) - 1)

    out = [
        "# What the snapshot shows",
        "",
        f"Taken on {when(s['taken_at'])} (`{s['taken_at']}`). Every figure here is plain arithmetic on this one "
        "snapshot of UK and Irish bookmaker prices. It describes the prices at that moment only: prices change all "
        "the time, so it is not a forecast and not advice.",
        "",
        "Every count here (events, bookmakers, markets, prices) describes this one snapshot file and nothing more. "
        "It is not a measure of what the OddsRelay feed covers.",
        "",
        f"- **Start times:** events scheduled to start between {s['window'][0]} and {s['window'][1]} (UTC).",
        f"- **Boards:** the raw board (markets `{RAW_MARKETS.replace(',', '`, `')}`) and the standard matched board "
        f"(markets `{STANDARD_MARKETS.replace(',', '`, `')}`, bookmaker prices only), read between {s['read'][0]} "
        f"and {s['read'][1]} (UTC).",
        "- **Venues:** bookmakers only. Every exchange, and every venue under the Betfair name, is left out.",
        f"- **The sample:** up to {PER_SPORT} events per sport with prices from two or more bookmakers: events on "
        "the matched board first, then those with the most bookmakers.",
        "",
        "## Events per sport",
        "",
        "| Sport | Events in this sample | Bookmakers per event (median) |",
        "|---|---:|---:|",
    ]
    for sport in sorted(sample, key=lambda x: (-len(sample[x]), x)):
        n = sample[sport]
        out.append(f"| {sport.replace('_', ' ')} | {len(n):,} | {statistics.median(n):g} |")
    out += [
        "",
        "One fixture can appear as two events on the raw board. The sample picks events with more bookmakers, so "
        "these medians run higher than a typical event's would, and the margins below describe these events only.",
        "",
        "## Margin on the result market",
        "",
        "A bookmaker's margin on one market is the sum of 1 / price over all its outcomes, minus 1. A market counts "
        "only when the bookmaker prices every outcome: as many outcomes as that sport's result markets most often "
        "have in this sample (three in soccer: home, draw, away).",
        "",
        "| Sport | Complete result markets | Median margin | Lowest | Highest |",
        "|---|---:|---:|---:|---:|",
    ]
    for sport in sorted(by_sport, key=lambda x: (-len(by_sport[x]), x)):
        m = by_sport[sport]
        out.append(f"| {sport.replace('_', ' ')} | {len(m):,} | {pct(statistics.median(m))} | {pct(min(m))} | "
                   f"{pct(max(m))} |")
    out += [
        "",
        "### Soccer, by bookmaker",
        "",
        f"Each bookmaker's mean margin on the soccer result market, for the bookmakers that priced it completely on "
        f"all {soccer_events} soccer events where this sample has a complete one, so every row averages the same "
        "events. A bookmaker priced on only some of them is left out. Listed alphabetically.",
        "",
        "| Bookmaker | Mean margin |",
        "|---|---:|",
    ]
    for book in sorted(by_book, key=lambda b: names[b].lower()):
        out.append(f"| {names[book]} | {pct(statistics.mean(by_book[book]))} |")
    out += [
        "",
        "## Spread of prices on the matched board",
        "",
        "For each outcome of the matched board's result market priced by two or more bookmakers: how far the "
        "highest price sits above the lowest, as highest / lowest - 1. The median per sport.",
        "",
        "| Sport | Outcomes | Median spread |",
        "|---|---:|---:|",
    ]
    for sport in sorted(spread, key=lambda x: (-len(spread[x]), x)):
        out.append(f"| {sport.replace('_', ' ')} | {len(spread[sport]):,} | {pct(statistics.median(spread[sport]))} |")
    out += ["", "## Files", "", "| File | Rows |", "|---|---:|"]
    out += [f"| `data/{name}.csv` | {n:,} |" for name, n in s["counts"].items()]
    out += ["", f"Licence: CC BY 4.0. Attribution: {ATTRIBUTION}.", ""]
    return "\n".join(out)


# ---- docs and metadata ----------------------------------------------------------------------------------------------

KAGGLE_TYPES = {"string": "string", "number": "numeric", "integer": "integer", "datetime": "datetime"}
JSON_FILES = {
    "raw_board.json": "The sample's raw-board events in the API's own shape, bookmakers only: meta, then data, one "
                      "object per event with each bookmaker's markets and outcomes.",
    "standard_board.json": "The sample's events on the standard matched board in the API's own shape, back prices "
                           "only: meta, then data, one object per event with its markets, outcomes and the "
                           "bookmakers' prices for each outcome, highest first.",
}


def datapackage(taken_at: str) -> dict:
    resources = []
    for table, (about, key, fields) in TABLES.items():
        schema = {"fields": [{"name": n, "type": t, "description": d,
                              **({"constraints": {"required": True}} if n in REQUIRED else {})}
                             for n, t, d in fields]}
        if key:
            schema["primaryKey"] = key
        schema["foreignKeys"] = [
            {"fields": f, "reference": {"resource": "events" if f == "event_id" else "bookmakers", "fields": f}}
            for f in FOREIGN.get(table, [])]
        resources.append({"name": table, "path": f"data/{table}.csv", "profile": "tabular-data-resource",
                          "format": "csv", "mediatype": "text/csv", "encoding": "utf-8", "description": about,
                          "schema": schema})
    for path, about in JSON_FILES.items():
        # "type": "json" is frictionless's own resource type: without it, frictionless reads a JSON file under 1 MB
        # whose top level has a "data" key (standard_board.json) as a resource descriptor and fails the package.
        resources.append({"name": path.split(".")[0].replace("_", "-"), "path": f"data/{path}", "type": "json",
                          "profile": "data-resource", "format": "json", "mediatype": "application/json",
                          "encoding": "utf-8", "description": about})
    return {
        "profile": "data-package",
        "name": "uk-bookmaker-prices-sample",
        "title": "UK and Irish bookmaker prices: a sample snapshot",
        "description": f"One snapshot, taken {taken_at}, of pre-match prices from UK and Irish bookmakers, from the "
                       "OddsRelay API's raw board and standard matched board. Bookmakers only: no exchange prices.",
        "homepage": "https://oddsrelay.io",
        "created": taken_at,
        "keywords": ["sports", "odds", "bookmakers", "football", "tennis", "horse racing", "uk", "ireland"],
        "licenses": [{"name": "CC-BY-4.0", "title": "Creative Commons Attribution 4.0",
                      "path": "https://creativecommons.org/licenses/by/4.0/"}],
        "contributors": [{"title": "OddsRelay", "path": "https://oddsrelay.io", "role": "author"}],
        "sources": [{"title": "OddsRelay API", "path": "https://oddsrelay.io/docs"}],
        "resources": resources,
    }


def kaggle(taken_at: str) -> dict:
    resources = [{"path": f"{t}.csv", "description": about,
                  "schema": {"fields": [{"name": n, "description": d, "type": KAGGLE_TYPES[ty]}
                                        for n, ty, d in fields]}}
                 for t, (about, _, fields) in TABLES.items()]
    resources += [{"path": p, "description": about} for p, about in JSON_FILES.items()]
    return {
        "title": "UK and Irish bookmaker prices: a sample snapshot",
        "subtitle": "One snapshot of pre-match prices from UK and Irish bookmakers",
        "description": (
            f"One snapshot, taken {when(taken_at)}, of pre-match prices from UK and Irish bookmakers, from the "
            "OddsRelay API: its raw board (each bookmaker's own markets and outcome names) and its standard matched "
            "board (every bookmaker's price on the same outcome under one name).\n\n"
            "Bookmakers only: every exchange, lay price and liquidity figure is left out. It is a sample: one moment, "
            "a few events per sport, a few markets. It has no history and no closing prices. Every count in it "
            "describes this snapshot only, not what the OddsRelay feed covers.\n\n"
            "Column meanings are in each file's description here and in DATA_DICTIONARY.md in the GitHub repository "
            "(https://github.com/oddsrelay/sample-data), which also holds the script that rebuilds it.\n\n"
            f"Licence: CC BY 4.0. Attribution: {ATTRIBUTION}.\n\n"
            "Current prices: https://oddsrelay.io/docs"),
        "id": "oddsrelay/uk-bookmaker-prices-sample",
        "licenses": [{"name": "CC-BY-4.0"}],
        "keywords": ["sports", "football", "tennis", "tabular", "united kingdom"],
        "resources": resources,
    }


def dictionary(markets_seen: set) -> str:
    out = ["# Data dictionary", "",
           "Every column of every file in `data/`. Types are the Frictionless types also used in `datapackage.json`. "
           "An empty cell in a CSV file means the value does not apply or was not given.", ""]
    for table, (about, key, fields) in TABLES.items():
        out += [f"## `data/{table}.csv`", "", about + (f" Key: `{', '.join(key)}`." if key else ""), "",
                "| Column | Type | Meaning |", "|---|---|---|"]
        out += [f"| `{n}` | {t} | {d} |" for n, t, d in fields]
        out.append("")
    out += ["## Market keys", "", "| Key | Meaning |", "|---|---|"]
    out += [f"| `{k}` | {MARKETS.get(k, 'See the API docs.')} |" for k in sorted(markets_seen)]
    out += ["", "## The JSON files", ""]
    out += [f"- `data/{p}`: {about}" for p, about in JSON_FILES.items()]
    out += ["",
            "In both, `meta` holds `feed_type`, `region` (`uk`: the UK and Ireland), `odds_format` (`decimal`), "
            "`processed_at` (when the board was produced, UTC; on the raw board, the first page's time) and `count` "
            "(events). Event fields match the CSV columns: `id` (raw) and `event_id` (matched) are `event_id`, "
            "`sport_title` is `competition`, `venue` is `course`. On the raw board each event has `bookmakers`: "
            "`key`, `title`, `last_update` (the latest of its markets) and `markets` (`key`, `last_update`, "
            "`outcomes` of `name` and `price`). On the matched board each event has `markets` (`key`, `outcomes`), "
            "and each outcome has `name`, `point` on line markets and `back`, the bookmakers' prices (`bookmaker`, "
            "`price`), highest first.", ""]
    return "\n".join(out)


# ---- the run --------------------------------------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Take one snapshot and rebuild the sample's files.")
    ap.add_argument("--max-tokens", type=int, required=True, help="the most this run may spend")
    args = ap.parse_args()
    meter = Meter(args.max_tokens)
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    stamp = lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731
    taken_at, window = stamp(now), (stamp(now), stamp(now + dt.timedelta(hours=HOURS)))

    venues = get("/v2/bookmakers", {})[1]["data"]
    books = {v["key"]: v["name"] for v in venues if not v["is_exchange"] and REGION in v["regions"]
             and not any(word in v["key"].lower() for word in LEFT_OUT)}
    coverage = get("/v2/coverage", {"region": REGION})[1]["products"]
    sports = {s for v in coverage.get("raw", {}).get("bookmakers", []) for s in v["sports"]}
    sport = lambda key: sport_of(key, sports)  # noqa: E731

    span = {"region": REGION, "commenceTimeFrom": window[0], "commenceTimeTo": window[1]}
    board = meter("/v2/odds/standard", {**span, "markets": STANDARD_MARKETS})
    matched = {e["event_id"]: strip_matched(e, set(books)) for e in board["data"]}
    matched = {k: e for k, e in matched.items() if e["markets"]}

    raw, raw_times, cursor = {}, [], None
    while True:
        page = meter("/v2/odds/raw", {**span, "markets": RAW_MARKETS, "includeLiquidity": "false", "limit": 250,
                                      "cursor": cursor})
        raw_times.append(iso(page["meta"]["processed_at"]))
        for event in page["data"]:
            raw.setdefault(event["id"], strip_raw(event, set(books)))
        cursor = page["meta"].get("next_cursor")
        if not cursor:
            break

    events_raw = pick(list(raw.values()), set(matched), sport, PER_SPORT)
    kept = {e["id"] for e in events_raw}
    events_matched = [matched[e["id"]] for e in events_raw if e["id"] in matched]
    events = event_rows(events_raw, matched, sport)
    rows_raw, rows_matched = list(raw_rows(events_raw)), list(matched_rows(events_matched))
    used = {r["bookmaker_key"] for r in rows_raw} | {r["bookmaker_key"] for r in rows_matched}
    bookmakers = [{"bookmaker_key": k, "bookmaker_name": books[k]} for k in sorted(used)]

    data = os.path.join(HERE, "data")
    os.makedirs(data, exist_ok=True)
    counts = {
        "bookmakers": write_csv(os.path.join(data, "bookmakers.csv"), "bookmakers", bookmakers),
        "events": write_csv(os.path.join(data, "events.csv"), "events", events),
        "raw_prices": write_csv(os.path.join(data, "raw_prices.csv"), "raw_prices", rows_raw),
        "matched_prices": write_csv(os.path.join(data, "matched_prices.csv"), "matched_prices", rows_matched),
    }
    meta = {"region": REGION, "odds_format": "decimal"}
    write_json(os.path.join(data, "raw_board.json"),
               {"meta": {"feed_type": "raw", **meta, "processed_at": raw_times[0], "count": len(events_raw)},
                "data": events_raw})
    write_json(os.path.join(data, "standard_board.json"),
               {"meta": {"feed_type": "standard", **meta, "processed_at": iso(board["meta"]["processed_at"]),
                         "count": len(events_matched)}, "data": events_matched})
    write_json(os.path.join(data, "dataset-metadata.json"), kaggle(taken_at))
    with open(os.path.join(HERE, "datapackage.json"), "w", encoding="utf-8") as f:
        json.dump(datapackage(taken_at), f, ensure_ascii=False, indent=2)
        f.write("\n")
    markets_seen = {r["market"] for r in rows_raw} | {r["market"] for r in rows_matched}
    with open(os.path.join(HERE, "DATA_DICTIONARY.md"), "w", encoding="utf-8") as f:
        f.write(dictionary(markets_seen))
    with open(os.path.join(HERE, "summary.md"), "w", encoding="utf-8") as f:
        read = raw_times + [iso(board["meta"]["processed_at"])]
        f.write(summary({"taken_at": taken_at, "window": window, "read": (min(read), max(read)),
                         "events": events, "raw_rows": rows_raw, "matched_rows": rows_matched,
                         "names": books, "counts": counts}))
    print(f"snapshot {taken_at}: {len(kept)} events, {counts['raw_prices']} raw and {counts['matched_prices']} "
          f"matched prices from {len(bookmakers)} bookmakers; {meter.spent} tokens spent")


if __name__ == "__main__":
    main()
