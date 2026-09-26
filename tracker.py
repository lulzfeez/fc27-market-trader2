import csv
import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

PLAYERS_FILE = "players.json"
HISTORY_FILE = "prices.csv"
SIGNALS_FILE = "signals.csv"
REPORT_FILE = "report.md"
BASE = "https://www.futbin.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FC27MarketTracker/1.0)", "Accept-Language": "en-US,en;q=0.9"}

def load_players():
    with open(PLAYERS_FILE, encoding="utf-8") as f:
        return json.load(f)

def parse_price(page_text):
    patterns = [
        r"current price on FUT is\s*([\d,]+)\s*on PlayStation,\s*([\d,]+)\s*on Xbox,\s*([\d,]+)\s*on PC",
        r"PlayStation[^\d]{0,80}([\d,]+).*?Xbox[^\d]{0,80}([\d,]+).*?PC[^\d]{0,80}([\d,]+)"
    ]
    for pattern in patterns:
        m = re.search(pattern, page_text, re.I | re.S)
        if m:
            return {"PlayStation": int(m.group(1).replace(",","")), "Xbox": int(m.group(2).replace(",","")), "PC": int(m.group(3).replace(",",""))}
    return None

def resolve_url(player):
    if player.get("url"):
        return player["url"]
    q = quote(player["name"])
    r = requests.get(f"{BASE}/27/players?page=1&search={q}", headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    wanted = re.sub(r"[^a-z0-9]","",player["name"].lower())
    candidates = []
    for a in soup.select('a[href*="/27/player/"]'):
        href = urljoin(BASE, a.get("href",""))
        label = a.get_text(" ", strip=True)
        norm = re.sub(r"[^a-z0-9]","",label.lower())
        score = 100 if norm == wanted else (50 if wanted in norm else 0)
        if score:
            candidates.append((score, href))
    if not candidates:
        raise RuntimeError("No matching FUTBIN player page found")
    candidates.sort(reverse=True)
    return candidates[0][1]

def fetch_player(player):
    url = resolve_url(player)
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    text = BeautifulSoup(response.text, "html.parser").get_text(" ", strip=True)
    prices = parse_price(text)
    if not prices:
        raise RuntimeError("Could not parse current prices from FUTBIN page")
    return url, prices

def read_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def append_rows(rows):
    fields=["timestamp_utc","player","url","platform","price","previous_price","change_coins","change_percent"]
    exists=os.path.exists(HISTORY_FILE) and os.path.getsize(HISTORY_FILE)>0
    with open(HISTORY_FILE,"a",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields)
        if not exists: w.writeheader()
        w.writerows(rows)

def write_analysis(history):
    latest={}
    for r in history:
        try: p=int(r["price"])
        except: continue
        key=(r["player"],r["platform"])
        latest[key]=r
    rows=[]
    for (player,platform),r in latest.items():
        rows.append({"player":player,"platform":platform,"price":int(r["price"]),"change_percent":r.get("change_percent","")})
    with open(SIGNALS_FILE,"w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["player","platform","price","change_percent"])
        w.writeheader(); w.writerows(rows)
    lines=["# FC 27 Market Report","","Latest observed prices and change versus the previous snapshot.","","| Player | Platform | Price | Change |","|---|---|---:|---:|"]
    for r in sorted(rows,key=lambda x:(x["platform"],x["player"])):
        ch=r["change_percent"] or "—"
        lines.append(f"| {r['player']} | {r['platform']} | {r['price']:,} | {ch}% |")
    lines += ["","","Data is descriptive historical tracking, not a prediction."]
    with open(REPORT_FILE,"w",encoding="utf-8") as f: f.write("\n".join(lines)+"\n")

def main():
    players=load_players()
    if len(players)!=20: raise SystemExit(f"Expected 20 players, found {len(players)}")
    history=read_history()
    previous={(r["player"],r["platform"]):int(r["price"]) for r in history if r.get("price","").isdigit()}
    timestamp=datetime.now(timezone.utc).isoformat()
    rows=[]
    for player in players:
        try:
            url,prices=fetch_player(player)
            player["url"]=url
            for platform,price in prices.items():
                old=previous.get((player["name"],platform))
                change=price-old if old is not None else None
                pct=(change/old*100) if old else None
                rows.append({"timestamp_utc":timestamp,"player":player["name"],"url":url,"platform":platform,"price":price,"previous_price":old if old is not None else "","change_coins":change if change is not None else "","change_percent":f"{pct:.2f}" if pct is not None else ""})
            print(f"OK {player['name']}: {prices}")
        except Exception as e:
            print(f"ERROR {player['name']}: {e}")
        time.sleep(2)
    with open(PLAYERS_FILE,"w",encoding="utf-8") as f: json.dump(players,f,indent=2,ensure_ascii=False)
    if not rows: raise SystemExit("No prices were collected")
    append_rows(rows)
    write_analysis(read_history())

if __name__=="__main__":
    main()
