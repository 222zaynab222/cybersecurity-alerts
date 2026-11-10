"""Checks prices listed in watchlist.json and posts to a Discord webhook on drops."""
import json
import os
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

WATCHLIST = Path("watchlist.json")
STATE = Path("state.json")
WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL")
HEADERS = {"User-Agent": "Mozilla/5.0 (personal price tracker)"}


def parse_price(text):
    """Pull the first number out of text like '$404.00' or 'USD 1,199'."""
    m = re.search(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?", text)
    return float(m.group(0).replace(",", "")) if m else None


def fetch_price(item):
    r = requests.get(item["url"], headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    el = soup.select_one(item["selector"])
    if el is None:
        raise ValueError("selector not found on page")
    price = parse_price(el.get_text(" ", strip=True))
    if price is None:
        raise ValueError("no number found in selected element")
    return price


def notify(message):
    print(message)
    if not WEBHOOK:
        print("(DISCORD_WEBHOOK_URL not set, skipping Discord post)")
        return
    requests.post(WEBHOOK, json={"content": message}, timeout=20).raise_for_status()


def main():
    items = json.loads(WATCHLIST.read_text())
    state = json.loads(STATE.read_text()) if STATE.exists() else {}

    for item in items:
        name = item["name"]
        old = state.get(name, {})
        try:
            price = fetch_price(item)
        except Exception as e:  # keep going if one site fails
            print(f"[{name}] error: {e}")
            if not old.get("error"):  # alert only the first time it breaks
                notify(f"⚠️ Couldn't check **{name}**: {e}. The page may have changed.")
            state[name] = {**old, "error": True}
            continue

        last = old.get("price")
        if last is not None and price < last:
            notify(f"💸 **{name}** dropped from {last:g} to {price:g}!\n{item['url']}")
        elif last is None:
            print(f"[{name}] first check, baseline price {price:g}")
        else:
            print(f"[{name}] no drop (now {price:g}, was {last:g})")

        state[name] = {"price": price, "error": False}

    STATE.write_text(json.dumps(state, indent=2))


if __name__ == "__main__":
    sys.exit(main())
