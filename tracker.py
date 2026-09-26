import csv
import json
import os
from datetime import datetime, timezone

import requests

PLAYERS_FILE = "players.json"
HISTORY_FILE = "prices.csv"

API_BASE = "https://www.futbin.org/futbin/api/27"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/plain, */*",
}


def load_players():
    with open(PLAYERS_FILE, encoding="utf-8") as f:
        return json.load(f)


def api_get(endpoint, params=None):
    url = f"{API_BASE}/{endpoint}"

    response = requests.get(
        url,
        params=params or {},
        headers=HEADERS,
        timeout=30,
    )

    response.raise_for_status()
    return response.json()


def find_player_id(player_name):
    data = api_get(
        "searchPlayersByName",
        {
            "playername": player_name,
            "year": 27,
        },
    )

    results = data.get("data", [])

    if not results:
        return None

    # Prefer an exact name match
    for player in results:
        name = str(
            player.get("playername")
            or player.get("name")
            or ""
        ).strip()

        if name.lower() == player_name.lower():
            return player.get("ID")

    # Otherwise use the first result
    return results[0].get("ID")


def get_price(player_id, platform="PS"):
    data = api_get(
        "fetchPriceInformation",
        {
            "playerresource": player_id,
            "platform": platform,
        },
    )

    price = data.get("LCPrice", 0)

    try:
        return int(price or 0)
    except (TypeError, ValueError):
        return 0


def main():

    players = load_players()

    timestamp = datetime.now(timezone.utc).isoformat()

    rows = []

    for player in players:

        name = player["name"]

        try:

            # Use saved FUTBIN ID if available
            player_id = player.get("futbin_id")

            # Otherwise find it
            if not player_id:
                player_id = find_player_id(name)

            if not player_id:
                print(f"ERROR {name}: FUTBIN ID not found")
                continue

            price = get_price(player_id, "PS")

            if price <= 0:
                print(f"ERROR {name}: no price returned")
                continue

            print(f"OK {name}: {price:,} coins")

            rows.append({
                "timestamp_utc": timestamp,
                "player": name,
                "futbin_id": player_id,
                "platform": "PS/Xbox",
                "price": price,
            })

            # Save ID so we don't need to search next time
            player["futbin_id"] = player_id

        except Exception as e:

            print(f"ERROR {name}: {e}")

    if not rows:
        raise SystemExit("No prices were collected")

    # Save player IDs
    with open(PLAYERS_FILE, "w", encoding="utf-8") as f:
        json.dump(players, f, indent=2, ensure_ascii=False)
        f.write("\n")

    file_exists = os.path.exists(HISTORY_FILE)

    with open(
        HISTORY_FILE,
        "a",
        encoding="utf-8",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=[
                "timestamp_utc",
                "player",
                "futbin_id",
                "platform",
                "price",
            ],
        )

        if not file_exists:
            writer.writeheader()

        writer.writerows(rows)

    print()
    print(f"Collected prices for {len(rows)} players.")


if __name__ == "__main__":
    main()
