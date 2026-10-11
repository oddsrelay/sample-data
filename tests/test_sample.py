"""Checks on the sample: its files against datapackage.json, no exchange data, no key, the metadata, the examples and
the script's own logic. No network and no key needed.

A wording check also runs when ODDSRELAY_GATE names the maintainers' wording checker; without it, that test skips.
"""
import csv
import importlib.util
import json
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import snapshot  # noqa: E402

EXCHANGES = {"betdaq", "betfair_exchange", "matchbook", "smarkets"}
EXCHANGE_FIELDS = {"lay", "lay_price", "back_price", "available", "exchange", "link", "links", "liquidity"}
KEY_SHAPE = re.compile(r"\bor_(?:live|pub|test)_[A-Za-z0-9]{8,}|\bBearer\s+[A-Za-z0-9._~+/-]{20,}")
DATETIME = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ")
SKIP = {".git", "__pycache__"}


def repo_files():
    for root, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP]
        for name in names:
            yield os.path.relpath(os.path.join(root, name), ROOT)


def text(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def load_json(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)


def read_csv(rel):
    with open(os.path.join(ROOT, rel), newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        return header, [dict(zip(header, row)) for row in reader]


def keys_in(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from keys_in(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from keys_in(v)


PACKAGE = load_json("datapackage.json")
TABULAR = [r for r in PACKAGE["resources"] if r["format"] == "csv"]


class FilesMatchTheSchema(unittest.TestCase):
    def test_every_file_parses(self):
        for rel in repo_files():
            if rel.endswith(".json"):
                load_json(rel)
            elif rel.endswith(".csv"):
                read_csv(rel)

    def test_tables_follow_datapackage(self):
        tables = {}
        for res in TABULAR:
            header, rows = read_csv(res["path"])
            fields = res["schema"]["fields"]
            self.assertEqual(header, [f["name"] for f in fields], res["path"])
            self.assertTrue(rows, f"{res['path']} is empty")
            for n, row in enumerate(rows, 2):
                for f in fields:
                    value, where = row[f["name"]], f"{res['path']}:{n} {f['name']}"
                    if value == "":
                        self.assertFalse(f.get("constraints", {}).get("required"), f"{where} is required")
                    elif f["type"] == "number":
                        float(value)
                    elif f["type"] == "integer":
                        int(value)
                    elif f["type"] == "datetime":
                        self.assertRegex(value, DATETIME, where)
            key = res["schema"].get("primaryKey")
            if key:
                values = [tuple(r[k] for k in key) for r in rows]
                self.assertEqual(len(values), len(set(values)), f"{res['path']}: repeated {key}")
            tables[res["name"]] = rows
        for res in TABULAR:
            for fk in res["schema"].get("foreignKeys", []):
                ref = fk["reference"]
                known = {r[ref["fields"]] for r in tables[ref["resource"]]}
                missing = {r[fk["fields"]] for r in tables[res["name"]]} - known
                self.assertFalse(missing, f"{res['name']}.{fk['fields']} not in {ref['resource']}: {missing}")

    def test_prices_are_decimal_odds(self):
        for name in ("raw_prices", "matched_prices"):
            for row in read_csv(f"data/{name}.csv")[1]:
                self.assertGreater(float(row["price"]), 0, name)

    def test_json_boards_agree_with_csv(self):
        raw = load_json("data/raw_board.json")["data"]
        matched = load_json("data/standard_board.json")["data"]
        self.assertEqual(sum(len(m["outcomes"]) for e in raw for b in e["bookmakers"] for m in b["markets"]),
                         len(read_csv("data/raw_prices.csv")[1]))
        self.assertEqual(sum(len(o["back"]) for e in matched for m in e["markets"] for o in m["outcomes"]),
                         len(read_csv("data/matched_prices.csv")[1]))
        events = {r["event_id"] for r in read_csv("data/events.csv")[1]}
        self.assertEqual({e["id"] for e in raw}, events)
        self.assertLessEqual({e["event_id"] for e in matched}, events)

    def test_every_market_is_explained(self):
        dictionary = text("DATA_DICTIONARY.md")
        for name in ("raw_prices", "matched_prices"):
            for market in {r["market"] for r in read_csv(f"data/{name}.csv")[1]}:
                self.assertIn(market, snapshot.MARKETS, f"{market}: add its meaning to MARKETS")
                self.assertIn(f"`{market}`", dictionary)
        for res in TABULAR:
            for f in res["schema"]["fields"]:
                self.assertIn(f"`{f['name']}`", dictionary)


class NoExchangeData(unittest.TestCase):
    def test_no_exchange_rows(self):
        for name in ("raw_prices", "matched_prices", "bookmakers"):
            keys = {r["bookmaker_key"] for r in read_csv(f"data/{name}.csv")[1]}
            self.assertFalse(keys & EXCHANGES, name)
            self.assertFalse({k for k in keys if "betfair" in k}, name)
        for name in ("raw_prices", "matched_prices"):
            self.assertFalse({r["market"] for r in read_csv(f"data/{name}.csv")[1] if r["market"].endswith("_lay")})

    def test_no_exchange_fields_or_links(self):
        for rel in ("data/raw_board.json", "data/standard_board.json"):
            self.assertFalse(set(keys_in(load_json(rel))) & EXCHANGE_FIELDS, rel)
        for res in TABULAR:
            self.assertFalse({f["name"] for f in res["schema"]["fields"]} & EXCHANGE_FIELDS, res["path"])
        for rel in repo_files():
            if rel.startswith("data/") and not rel.endswith("dataset-metadata.json"):
                body = text(rel)
                self.assertNotRegex(body, r"(?i)betfair", rel)
                self.assertNotIn("http", body, rel)


class NoKey(unittest.TestCase):
    def test_no_key_shaped_string_anywhere(self):
        for rel in repo_files():
            try:
                body = text(rel)
            except UnicodeDecodeError:
                continue
            self.assertIsNone(KEY_SHAPE.search(body), rel)

    def test_the_key_in_this_shell_is_nowhere(self):
        key = (os.environ.get("ODDSRELAY_KEY") or os.environ.get("OR_KEY") or "").strip()
        if not key:
            self.skipTest("no key in this shell")
        for rel in repo_files():
            with open(os.path.join(ROOT, rel), "rb") as f:
                self.assertNotIn(key.encode(), f.read(), rel)


class Wording(unittest.TestCase):
    def test_wording_gate(self):
        path = os.environ.get("ODDSRELAY_GATE")
        if not path:
            self.skipTest("set ODDSRELAY_GATE to the wording checker to run this")
        spec = importlib.util.spec_from_file_location("gate", path)
        gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gate)
        words = [re.compile(gate.CHECKS[name]) for name in ("method", "trace")]
        for rel in repo_files():
            try:
                lines = text(rel).splitlines()
            except UnicodeDecodeError:
                continue
            for n, line in enumerate(lines, 1):
                for rx in words:
                    self.assertIsNone(rx.search(line), f"{rel}:{n}")


class Metadata(unittest.TestCase):
    def test_kaggle(self):
        meta = load_json("data/dataset-metadata.json")
        self.assertTrue(6 <= len(meta["title"]) <= 50)
        self.assertTrue(20 <= len(meta["subtitle"]) <= 80)
        self.assertEqual(meta["licenses"], [{"name": "CC-BY-4.0"}])
        self.assertRegex(meta["id"], r"^[a-z0-9-]+/[a-z0-9-]{3,50}$")
        for res in meta["resources"]:
            self.assertTrue(os.path.exists(os.path.join(ROOT, "data", res["path"])), res["path"])
            if res["path"].endswith(".csv"):
                header = read_csv(f"data/{res['path']}")[0]
                self.assertEqual([f["name"] for f in res["schema"]["fields"]], header, res["path"])

    def test_hugging_face_card(self):
        card = text("huggingface/README.md")
        head = card.split("---\n")[1]
        self.assertIn("license: cc-by-4.0", head)
        for path in re.findall(r"data_files: (\S+)", head):
            self.assertTrue(os.path.exists(os.path.join(ROOT, path)), path)
        rows = len(read_csv("data/raw_prices.csv")[1])
        bucket = "1K<n<10K" if rows < 10_000 else "10K<n<100K" if rows < 100_000 else "100K<n<1M"
        self.assertIn(f"- {bucket}", head)

    def test_datapackage(self):
        self.assertEqual(PACKAGE["licenses"][0]["name"], "CC-BY-4.0")
        for res in PACKAGE["resources"]:
            self.assertTrue(os.path.exists(os.path.join(ROOT, res["path"])), res["path"])
            if res["format"] == "json":  # else frictionless validate takes standard_board.json for a descriptor
                self.assertEqual(res.get("type"), "json", res["path"])


class Examples(unittest.TestCase):
    def run_example(self, name):
        done = subprocess.run([sys.executable, os.path.join(ROOT, "examples", name)], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(done.stdout.strip())

    def test_stdlib_example(self):
        self.run_example("load_stdlib.py")

    def test_pandas_example(self):
        if importlib.util.find_spec("pandas") is None:
            self.skipTest("pandas is not installed")
        self.run_example("load_pandas.py")


class Script(unittest.TestCase):
    BOOKS = {"book_a", "book_b"}

    def test_strip_raw_keeps_bookmaker_prices_only(self):
        event = {"id": "e1", "cluster_id": None, "sport_key": "soccer_x", "sport_title": "X",
                 "commence_time": "2026-10-12T19:45:00Z", "home_team": "A", "away_team": "B", "bookmakers": [
                     {"key": "book_a", "title": "Book A", "region": "uk", "last_update": "2026-10-11T20:00:01Z",
                      "markets": [{"key": "h2h", "last_update": "2026-10-11T20:00:01.500Z",
                                   "outcomes": [{"name": "A", "price": 2.1}, {"name": "B", "price": None}]}]},
                     {"key": "betfair_exchange", "title": "Exchange", "region": "uk", "last_update": None,
                      "markets": [{"key": "h2h", "last_update": None, "outcomes": [{"name": "A", "price": 2.2}]}]},
                     {"key": "book_b", "title": "Book B", "region": "uk", "last_update": None, "markets": [
                         {"key": "h2h_lay", "last_update": None,
                          "outcomes": [{"name": "A", "back_price": None, "lay_price": 2.3, "available": 9.0}]},
                         {"key": "btts", "last_update": None,
                          "outcomes": [{"name": "Yes", "lay_price": 1.9}]}]}]}
        out = snapshot.strip_raw(event, self.BOOKS)
        self.assertNotIn("cluster_id", out)
        self.assertEqual([v["key"] for v in out["bookmakers"]], ["book_a"])
        self.assertEqual(out["bookmakers"][0]["markets"],
                         [{"key": "h2h", "last_update": "2026-10-11T20:00:01Z", "outcomes": [{"name": "A", "price": 2.1}]}])

    def test_strip_matched_drops_lay_links_and_exchanges(self):
        event = {"event_id": "e1", "sport_key": "soccer_x", "sport_title": "X", "commence_time": "2026-10-12T19:45:00Z",
                 "home_team": "A", "away_team": "B", "markets": [{"key": "totals", "outcomes": [
                     {"name": "Over", "point": 2.5,
                      "back": [{"bookmaker": "book_b", "price": 1.9, "link": "x"},
                               {"bookmaker": "smarkets", "price": 1.95, "link": "y"}],
                      "lay": [{"exchange": "smarkets", "price": 2.0, "available": 50.0, "link": "z"}]},
                     {"name": "Under", "point": 2.5, "back": [{"bookmaker": "smarkets", "price": 2.0, "link": "y"}],
                      "lay": []}]}]}
        out = snapshot.strip_matched(event, self.BOOKS)
        self.assertEqual(out["markets"], [{"key": "totals", "outcomes": [
            {"name": "Over", "point": 2.5, "back": [{"bookmaker": "book_b", "price": 1.9}]}]}])

    def test_overround(self):
        self.assertAlmostEqual(snapshot.overround([2.0, 3.5, 4.0]), 0.5 + 1 / 3.5 + 0.25 - 1)
        self.assertAlmostEqual(snapshot.overround([2.0, 2.0]), 0.0)

    def test_result_margins_keep_complete_markets_only(self):
        rows = [{"event_id": "e1", "bookmaker_key": b, "market": "h2h", "price": p}
                for b, ps in (("a", [2.0, 3.5, 4.0]), ("b", [2.0, 3.5, 4.0]), ("c", [2.0, 3.5])) for p in ps]
        margins = snapshot.result_margins(rows, {"e1": "soccer"})
        self.assertEqual(sorted(b for _, b, _ in margins), ["a", "b"])

    def test_sport_of_takes_the_longest_sport(self):
        sports = {"soccer", "horse_racing", "american_football"}
        self.assertEqual(snapshot.sport_of("horse_racing", sports), "horse_racing")
        self.assertEqual(snapshot.sport_of("american_football_nfl", sports), "american_football")
        self.assertEqual(snapshot.sport_of("darts_pdc", sports), "darts")

    def test_pick_prefers_matched_then_most_bookmakers(self):
        def ev(i, books, when):
            return {"id": i, "sport_key": "soccer_x", "commence_time": when, "bookmakers": [{}] * books}
        raw = [ev("a", 5, "2026-10-12T10:00:00Z"), ev("b", 9, "2026-10-12T11:00:00Z"),
               ev("c", 2, "2026-10-12T09:00:00Z"), ev("d", 1, "2026-10-12T08:00:00Z")]
        kept = snapshot.pick(raw, {"c"}, lambda key: "soccer", 2)
        self.assertEqual([e["id"] for e in kept], ["c", "b"])


if __name__ == "__main__":
    unittest.main()
