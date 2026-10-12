# What the snapshot shows

Taken on 11 October 2026 at 20:16 UTC (`2026-10-11T20:16:34Z`). Every figure here is plain arithmetic on this one snapshot of UK and Irish bookmaker prices. It describes the prices at that moment only: prices change all the time, so it is not a forecast and not advice.

Every count here (events, bookmakers, markets, prices) describes this one snapshot file and nothing more. It is not a measure of what the OddsRelay feed covers.

- **Start times:** events scheduled to start between 2026-10-11T20:16:34Z and 2026-10-12T20:16:34Z (UTC).
- **Boards:** the raw board (markets `h2h`, `btts`, `outright_winner`) and the standard matched board (markets `h2h`, `totals`, `btts`, `win`, bookmaker prices only), read between 2026-10-11T20:16:31Z and 2026-10-11T20:16:35Z (UTC).
- **Venues:** bookmakers only. Every exchange, and every venue under the Betfair name, is left out.
- **The sample:** up to 15 events per sport with prices from two or more bookmakers: events on the matched board first, then those with the most bookmakers.

## Events per sport

| Sport | Events in this sample | Bookmakers per event (median) |
|---|---:|---:|
| basketball | 15 | 36 |
| cricket | 15 | 19 |
| darts | 15 | 42 |
| esports | 15 | 21 |
| handball | 15 | 9 |
| horse racing | 15 | 50 |
| ice hockey | 15 | 35 |
| soccer | 15 | 60 |
| table tennis | 15 | 27 |
| tennis | 15 | 53 |
| volleyball | 15 | 8 |
| baseball | 7 | 44 |
| american football | 6 | 51 |
| golf | 6 | 2 |
| gaelic football | 1 | 4 |
| greyhound racing | 1 | 5 |

One fixture can appear as two events on the raw board. The sample picks events with more bookmakers, so these medians run higher than a typical event's would, and the margins below describe these events only.

## Margin on the result market

A bookmaker's margin on one market is the sum of 1 / price over all its outcomes, minus 1. A market counts only when the bookmaker prices every outcome: as many outcomes as that sport's result markets most often have in this sample (three in soccer: home, draw, away).

| Sport | Complete result markets | Median margin | Lowest | Highest |
|---|---:|---:|---:|---:|
| soccer | 901 | 8.7% | 2.8% | 22.2% |
| tennis | 813 | 7.8% | 4.7% | 12.6% |
| basketball | 558 | 8.1% | 3.8% | 17.7% |
| darts | 554 | 8.2% | 6.3% | 11.0% |
| ice hockey | 518 | 7.8% | 2.7% | 12.1% |
| table tennis | 433 | 9.1% | 6.6% | 15.4% |
| esports | 336 | 8.3% | 5.1% | 13.2% |
| cricket | 284 | 7.9% | 3.3% | 12.3% |
| baseball | 249 | 7.0% | 3.9% | 10.2% |
| american football | 240 | 6.2% | 2.3% | 9.9% |
| handball | 187 | 12.0% | 7.4% | 18.3% |
| volleyball | 139 | 8.3% | 6.4% | 10.5% |
| gaelic football | 4 | 12.4% | 11.4% | 13.4% |

### Soccer, by bookmaker

Each bookmaker's mean margin on the soccer result market, for the bookmakers that priced it completely on all 15 soccer events where this sample has a complete one, so every row averages the same events. A bookmaker priced on only some of them is left out. Listed alphabetically.

| Bookmaker | Mean margin |
|---|---:|
| 7bet | 9.2% |
| 888sport | 9.4% |
| Bally Bet | 8.3% |
| Bet Target | 8.4% |
| Betano | 7.5% |
| Betfred | 8.8% |
| BetMGM | 10.0% |
| Betnero | 8.0% |
| BetUK | 13.0% |
| BetVictor | 7.5% |
| Betway | 7.6% |
| BetWright | 12.8% |
| Bwin | 8.2% |
| Casumo | 8.3% |
| Coral | 8.6% |
| Dabble | 8.1% |
| Double Bubble Bingo | 8.3% |
| DragonBet | 12.8% |
| FanTeam | 8.4% |
| Fitzdares | 10.3% |
| Grosvenor | 8.0% |
| Hopa | 8.4% |
| Jackpotjoy | 8.3% |
| Karamba | 8.4% |
| Ladbrokes | 8.9% |
| LiveScore Bet | 11.4% |
| Lottoland | 9.2% |
| McBookie | 6.6% |
| Monopoly Casino | 8.3% |
| Mr Vegas | 6.6% |
| Parimatch | 7.5% |
| Planet Sport Bet | 12.8% |
| PricedUP | 12.8% |
| Pub Casino | 8.2% |
| Puntit | 7.5% |
| Rainbow Riches Casino | 8.3% |
| Sky Bet | 10.7% |
| Sporting Index | 6.9% |
| Sportingbet | 7.9% |
| Spreadex | 6.9% |
| Star Sports | 12.8% |
| talkSPORT Bet | 7.5% |
| Tote | 16.2% |
| Unibet | 6.4% |
| Virgin Bet | 11.7% |
| William Hill | 9.5% |

## Spread of prices on the matched board

For each outcome of the matched board's result market priced by two or more bookmakers: how far the highest price sits above the lowest, as highest / lowest - 1. The median per sport.

| Sport | Outcomes | Median spread |
|---|---:|---:|
| tennis | 54 | 4.7% |
| soccer | 50 | 13.9% |
| basketball | 41 | 6.2% |
| ice hockey | 30 | 5.6% |
| darts | 22 | 4.7% |
| american football | 15 | 7.0% |
| esports | 15 | 4.8% |
| baseball | 12 | 5.0% |
| cricket | 11 | 3.2% |
| handball | 4 | 3.5% |

## Files

| File | Rows |
|---|---:|
| `data/bookmakers.csv` | 66 |
| `data/events.csv` | 186 |
| `data/raw_prices.csv` | 20,374 |
| `data/matched_prices.csv` | 15,820 |

Licence: CC BY 4.0. Attribution: OddsRelay (https://oddsrelay.io).
