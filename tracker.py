import csv
import json
import os
from datetime import datetime, timezone

import requests

PLAYERS_FILE = "players.json"
HISTORY_FILE = "prices.csv"

# FUTBIN uses different paths for player search and price lookup.
SEARCH_API_BASE = "https://www.futbin.org/futbin/api"
PRICE_API_BASE = "https://www.futbin.org/futbin/api/27"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


def load_players():
    with open(PLAYERS_FILE, encoding="utf-8") as f:
        return json.load(f)


def api_get(url, params=None):
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
        f"{SEARCH_API_BASE}/searchPlayersByName",
        {
            "playername": player_name,
            "year": 27,
        },
    )

    results = data.get("data", [])
    if not isinstance(results, list) or not results:
        return None

    # FUTBIN search can return multiple card versions.
    # Prefer an exact name match, then the first result.
    for player in results:
        name = str(
            player.get("playername")
            or player.get("name")
            or ""
        ).strip()

        if name.lower() == player_name.lower():
            value = player.get("ID") or player.get("id")
            if value:
                return int(value)

    value = results[0].get("ID") or results[0].get("id")
    return int(value) if value else None


def get_price(player_id, platform="PS"):
    data = api_get(
        f"{PRICE_API_BASE}/fetchPriceInformation",
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
            player_id = player.get("futbin_id")

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

            player["futbin_id"] = player_id

            rows.append({
                "timestamp_utc": timestamp,
                "player": name,
                "futbin_id": player_id,
                "platform": "PS/Xbox",
                "price": price,
            })

        except Exception as e:
            print(f"ERROR {name}: {e}")

    if not rows:
        raise SystemExit("No prices were collected")

    with open(PLAYERS_FILE, "w", encoding="utf-8") as f:
        json.dump(players, f, indent=2, ensure_ascii=False)
        f.write("\n")

    file_exists = os.path.exists(HISTORY_FILE)

    with open(HISTORY_FILE, "a", encoding="utf-8", newline="") as f:
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
