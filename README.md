# FC 27 FUT Market Trader

Automated FC 27 FUT market tracker and trading analysis.

## What it does
- Tracks 20 FC 27 players.
- Resolves player pages on FUTBIN when a URL is not already stored.
- Collects PlayStation, Xbox and PC prices.
- Runs automatically every 2 hours through GitHub Actions.
- Stores historical snapshots in `prices.csv`.
- Calculates change versus the previous snapshot.
- Produces `signals.csv` and `report.md`.
- Supports manual runs with GitHub Actions.

## Files
- `players.json` — 20-player watchlist.
- `tracker.py` — collection and analysis engine.
- `prices.csv` — historical price database.
- `signals.csv` — latest observed movement.
- `report.md` — readable market report.
- `.github/workflows/market-tracker.yml` — two-hour automation.

## Automation
The workflow is scheduled at minute 17 of every even UTC hour and can also be started manually from the **Actions** tab.

## Notes
FUTBIN can change page structure or restrict automated requests. The tracker logs failed players and will not treat missing prices as valid data. Historical movement is descriptive and is not a guarantee of future performance.
