# FC 27 FUT Market Trader

Automated FC 27 FUT market tracker and trading analysis.

## What it does
- Tracks 20 FC 27 players.
- Collects market prices on a two-hour GitHub Actions schedule.
- Stores every snapshot in `prices.csv`.
- Calculates 2h, 6h, 24h and 7d observed price changes.
- Produces `signals.csv` and a readable `report.md`.
- Can also be run manually with GitHub Actions.

## Files
- `players.csv` — watchlist.
- `tracker.py` — collector and analysis engine.
- `prices.csv` — historical snapshots.
- `signals.csv` — latest movement metrics.
- `report.md` — latest human-readable report.
- `.github/workflows/market-tracker.yml` — automated schedule.

## Important
The tracker uses publicly accessible FUTBIN pages/data and is designed to tolerate page changes, but automated requests can be blocked or FUTBIN can change its page structure. Failed player lookups are logged rather than treated as valid prices.

The movement score describes observed historical movement; it is not a forecast or a guarantee of future performance.
