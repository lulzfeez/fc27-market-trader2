import csv
import json
import os
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

PLAYERS_FILE = "players.json"
HISTORY_FILE = "prices.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FC27MarketTracker/1.0)"
}

def load_players():
    with open(PLAYERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def parse_price(page_text):
    # FUTBIN pages commonly expose a sentence such as:
    # "His current price on FUT is 10,000 on PlayStation, 10,000 on Xbox, and 9,500 on PC."
    pattern = re.compile(
        r"current price on FUT is\s*([\d,]+)\s*on PlayStation,\s*([\d,]+)\s*on Xbox,\s*([\d,]+)\s*on PC",
        re.IGNORECASE,
    )
    match = pattern.search(page_text)
    if not match:
        return None

    return {
        "PlayStation": int(match.group(1).replace(",", "")),
        "Xbox": int(match.group(2).replace(",", "")),
        "PC": int(match.group(3).replace(",", "")),
    }

def fetch_player(player):
    response = requests.get(player["url"], headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    text = soup.get_text(" ", strip=True)
    prices = parse_price(text)

    if not prices:
        raise RuntimeError(f"Could not find current price on FUTBIN page for {player['name']}")

    return prices

def read_history():
    if not os.path.exists(HISTORY_FILE):
        return []

    with open(HISTORY_FILE, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def append_rows(rows):
    exists = os.path.exists(HISTORY_FILE)
    fields = [
        "timestamp_utc",
        "player",
        "url",
        "platform",
        "price",
        "previous_price",
        "change_coins",
        "change_percent",
    ]

    with open(HISTORY_FILE, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if not exists:
            writer.writeheader()
        writer.writerows(rows)

def main():
    players = load_players()
    history = read_history()

    # Most recent price for each player/platform.
    previous = {}
    for row in history:
        key = (row["player"], row["platform"])
        previous[key] = int(row["price"])

    timestamp = datetime.now(timezone.utc).isoformat()
    rows = []

    for player in players:
        try:
            prices = fetch_player(player)
            for platform, price in prices.items():
                old = previous.get((player["name"], platform))
                change = price - old if old is not None else None
                pct = (change / old * 100) if old else None

                rows.append({
                    "timestamp_utc": timestamp,
                    "player": player["name"],
                    "url": player["url"],
                    "platform": platform,
                    "price": price,
                    "previous_price": old if old is not None else "",
                    "change_coins": change if change is not None else "",
                    "change_percent": f"{pct:.2f}" if pct is not None else "",
                })

            print(f"OK: {player['name']} -> {prices}")
        except Exception as exc:
            print(f"ERROR: {player['name']}: {exc}")

        # Be polite to the site.
        time.sleep(2)

    if rows:
        append_rows(rows)
        print(f"Recorded {len(rows)} price observations.")
    else:
        raise SystemExit("No prices were collected.")

if __name__ == "__main__":
    main()
