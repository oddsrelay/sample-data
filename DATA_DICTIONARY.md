# Data dictionary

Every column of every file in `data/`. Types are the Frictionless types also used in `datapackage.json`. An empty cell in a CSV file means the value does not apply or was not given.

## `data/bookmakers.csv`

One row per bookmaker with at least one price in this sample. Key: `bookmaker_key`.

| Column | Type | Meaning |
|---|---|---|
| `bookmaker_key` | string | Short identifier of the bookmaker, the same one the API uses. Joins to the price tables. |
| `bookmaker_name` | string | The bookmaker's name as it is displayed. |

## `data/events.csv`

One row per event in this sample. On the raw board one fixture can appear as two events when bookmakers name or time it differently: compare sides and start times before counting fixtures. Key: `event_id`.

| Column | Type | Meaning |
|---|---|---|
| `event_id` | string | Identifier of the event in the API. Use it to join these files; it is not meant as a permanent key. |
| `sport` | string | The sport, for example soccer, tennis or horse_racing. |
| `sport_key` | string | The competition's identifier, which starts with the sport. |
| `competition` | string | The competition's name, or the sport's name where there is no competition. |
| `commence_time` | datetime | Scheduled start, in UTC. |
| `home_team` | string | The home side, or the first-named player. Empty for events without sides, such as races. |
| `away_team` | string | The away side, or the second-named player. Empty for events without sides. |
| `event_name` | string | The event's name where it does not split into two sides. Often empty. |
| `course` | string | Racing only: the racecourse, where the matched board names it. Otherwise empty. |

## `data/raw_prices.csv`

One row per price on the raw board: one bookmaker, one event, one market, one outcome. Outcome names are each bookmaker's own.

| Column | Type | Meaning |
|---|---|---|
| `event_id` | string | The event (events.csv). |
| `bookmaker_key` | string | The bookmaker (bookmakers.csv). |
| `market` | string | The market's key (DATA_DICTIONARY.md says what each one means). |
| `outcome` | string | The selection, worded as this bookmaker words it. |
| `price` | number | Decimal price: what one unit staked returns if the outcome wins, stake included. |
| `last_update` | datetime | When this bookmaker's prices on this market last changed, in UTC. |

## `data/matched_prices.csv`

One row per bookmaker price on the standard matched board, where every bookmaker's offer on the same outcome sits under one outcome name. Exchange prices are left out.

| Column | Type | Meaning |
|---|---|---|
| `event_id` | string | The event (events.csv). |
| `market` | string | The market's key (DATA_DICTIONARY.md says what each one means). |
| `outcome` | string | The selection, named once for every bookmaker. |
| `point` | number | The line on a line market, for example 2.5 on totals. Empty on other markets. |
| `bookmaker_key` | string | The bookmaker (bookmakers.csv). |
| `price` | number | Decimal price, as in raw_prices.csv. |

## Market keys

| Key | Meaning |
|---|---|
| `btts` | Both teams to score: yes or no. |
| `h2h` | The result. Two outcomes (one side or the other) or three where a draw is possible (home, draw, away). |
| `outright_winner` | The winner of a race or field: one outcome per runner. |
| `totals` | The total goals or points, over or under the line in point. |
| `win` | Racing: the winner of the race, one outcome per runner. |

## The JSON files

- `data/raw_board.json`: The sample's raw-board events in the API's own shape, bookmakers only: meta, then data, one object per event with each bookmaker's markets and outcomes.
- `data/standard_board.json`: The sample's events on the standard matched board in the API's own shape, back prices only: meta, then data, one object per event with its markets, outcomes and the bookmakers' prices for each outcome, highest first.

In both, `meta` holds `feed_type`, `region` (`uk`: the UK and Ireland), `odds_format` (`decimal`), `processed_at` (when the board was produced, UTC; on the raw board, the first page's time) and `count` (events). Event fields match the CSV columns: `id` (raw) and `event_id` (matched) are `event_id`, `sport_title` is `competition`, `venue` is `course`. On the raw board each event has `bookmakers`: `key`, `title`, `last_update` (the latest of its markets) and `markets` (`key`, `last_update`, `outcomes` of `name` and `price`). On the matched board each event has `markets` (`key`, `outcomes`), and each outcome has `name`, `point` on line markets and `back`, the bookmakers' prices (`bookmaker`, `price`), highest first.
