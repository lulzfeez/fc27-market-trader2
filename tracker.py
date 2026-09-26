import csv
import json
import os
import re
from datetime import datetime, timezone

import requests

PLAYERS_FILE = "players.json"
HISTORY_FILE = "prices.csv"
SIGNALS_FILE = "signals.csv"
REPORT_FILE = "report.md"

# FUTBIN blocks many GitHub Actions runner IPs at the website layer (403).
# Use the unofficial FUTBIN JSON API instead of scraping HTML pages.
API_BASE = "https://www.futbin.org/futbin/api"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FC27MarketTracker/1.0)",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.futbin.com/",
    "Origin": "https://www.futbin.com",
}
PLATFORMS = {"PlayStation": "PS", "Xbox": "XB", "PC": "PC"}


def load_players():
    with open(PLAYERS_FILE, encoding="utf-8") as f:
        return json.load(f)


def normalize_name(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def api_get(endpoint, params=None):
    response = requests.get(
        f"{API_BASE}/{endpoint}",
        params=params or {},
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def extract_players(payload):
    data = payload.get("data", payload)
    if isinstance(data, dict):
        for key in ("data", "players", "results"):
            if isinstance(data.get(key), list):
                return data[key]
    if isinstance(data, list):
        return data
    return []


def player_name(item):
    return str(item.get("playername") or item.get("name") or "").strip()


def player_id(item):
    value = item.get("ID") or item.get("id") or item.get("playerid")
    return int(value) if str(value).isdigit() else None


def resolve_ids(players):
    unresolved = {normalize_name(p["name"]): p for p in players if not p.get("futbin_id")}
    if not unresolved:
        return

    found = {}
    for page in range(1, 41):
        payload = api_get(
            "getFilteredPlayers",
            {"platform": "PS", "page": page, "min_rating": 80},
        )
        rows = extract_players(payload)
        if not rows:
            break

        for item in rows:
            name = normalize_name(player_name(item))
            pid = player_id(item)
            if name in unresolved and pid:
                found[name] = pid

        if len(found) == len(unresolved):
            break

    missing = []
    for key, player in unresolved.items():
        if key in found:
            player["futbin_id"] = found[key]
        else:
            missing.append(player["name"])

    if missing:
        raise RuntimeError(
            "Could not resolve FUTBIN IDs for: " + ", ".join(missing)
        )


def get_prices(players):
    ids = [str(p["futbin_id"]) for p in players]
    payloads = {}

    # FUTBIN treats PS/Xbox as one console market; record both labels.
    for label, platform in PLATFORMS.items():
        payloads[label] = api_get(
            "getPlayersPrice",
            {"player_ids": ",".join(ids), "platform": platform},
        )

    prices = {}
    for player in players:
        pid = str(player["futbin_id"])
        prices[player["name"]] = {}
        for label, platform in PLATFORMS.items():
            entry = (
                payloads[label]
                .get(pid, {})
                .get("prices", {})
                .get(platform, {})
            )
            raw = entry.get("LCPrice", 0) if isinstance(entry, dict) else 0
            try:
                value = int(raw or 0)
            except (TypeError, ValueError):
                value = 0
            prices[player["name"]][label] = value
    return prices


def read_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def append_rows(rows):
    fields = [
        "timestamp_utc",
        "player",
        "futbin_id",
        "platform",
        "price",
        "previous_price",
        "change_coins",
        "change_percent",
    ]
    with open(HISTORY_FILE, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writerows(rows)


def write_analysis(history):
    latest = {}
    for row in history:
        try:
            price = int(row["price"])
        except (KeyError, TypeError, ValueError):
            continue
        latest[(row["player"], row["platform"])] = {
            "player": row["player"],
            "platform": row["platform"],
            "price": price,
            "change_percent": row.get("change_percent", ""),
        }

    rows = list(latest.values())
    with open(SIGNALS_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["player", "platform", "price", "change_percent"]
        )
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# FC 27 Market Report",
        "",
        "Latest observed prices and change versus the previous snapshot.",
        "",
        "| Player | Platform | Price | Change |",
        "|---|---|---:|---:|",
    ]
    for row in sorted(rows, key=lambda x: (x["platform"], x["player"])):
        change = row["change_percent"] or "—"
        lines.append(
            f"| {row['player']} | {row['platform']} | "
            f"{row['price']:,} | {change}% |"
        )
    lines += [
        "",
        "Data is descriptive historical tracking, not a prediction.",
    ]
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    players = load_players()
    if len(players) != 20:
        raise SystemExit(f"Expected 20 players, found {len(players)}")

    resolve_ids(players)

    history = read_history()
    previous = {}
    for row in history:
        try:
            previous[(row["player"], row["platform"])] = int(row["price"])
        except (KeyError, TypeError, ValueError):
            continue

    prices = get_prices(players)
    timestamp = datetime.now(timezone.utc).isoformat()
    rows = []

    for player in players:
        name = player["name"]
        player_prices = prices.get(name, {})
        if not any(player_prices.values()):
            print(f"ERROR {name}: no market prices returned")
            continue

        print(f"OK {name}: {player_prices}")
        for platform, price in player_prices.items():
            if price <= 0:
                continue
            old = previous.get((name, platform))
            change = price - old if old is not None else None
            pct = (change / old * 100) if old else None
            rows.append(
                {
                    "timestamp_utc": timestamp,
                    "player": name,
                    "futbin_id": player["futbin_id"],
                    "platform": platform,
                    "price": price,
                    "previous_price": old if old is not None else "",
                    "change_coins": change if change is not None else "",
                    "change_percent": f"{pct:.2f}" if pct is not None else "",
                }
            )

    with open(PLAYERS_FILE, "w", encoding="utf-8") as f:
        json.dump(players, f, indent=2, ensure_ascii=False)
        f.write("\n")

    if not rows:
        raise SystemExit("No prices were collected")

    append_rows(rows)
    write_analysis(read_history())


if __name__ == "__main__":
    main()
