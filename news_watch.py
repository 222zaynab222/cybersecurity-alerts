"""Reads cybersecurity RSS feeds and posts NEW items to a Discord webhook."""
import json
import os
import sys
from pathlib import Path

import feedparser
import requests

FEEDS = Path("feeds.json")
SEEN = Path("seen.json")
WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL")
UA = "Mozilla/5.0 (personal cyber news tracker)"
EMOJI = {"attack": "🚨", "tech": "🧪", "law": "⚖️"}
MAX_POSTS_PER_RUN = 15
KEEP_IDS = 300  # remembered IDs per feed


def notify(message):
    print(message)
    if not WEBHOOK:
        print("(DISCORD_WEBHOOK_URL not set, skipping Discord post)")
        return
    requests.post(WEBHOOK, json={"content": message[:1900]}, timeout=20).raise_for_status()


def matches(entry, keywords):
    if not keywords:
        return True
    text = f"{entry.get('title', '')} {entry.get('summary', '')}".lower()
    return any(k.lower() in text for k in keywords)


def main():
    feeds = json.loads(FEEDS.read_text())
    first_run = not SEEN.exists()
    seen = {} if first_run else json.loads(SEEN.read_text())
    posted = 0
    skipped = 0

    for feed in feeds:
        name = feed["name"]
        parsed = feedparser.parse(feed["url"], agent=UA)
        if not parsed.entries:
            print(f"[{name}] no entries (feed down or URL wrong?)")
            continue

        known = set(seen.get(name, []))
        ids = list(seen.get(name, []))
        # oldest first so messages appear in order
        for entry in reversed(parsed.entries):
            eid = entry.get("id") or entry.get("link")
            if not eid or eid in known:
                continue
            known.add(eid)
            ids.append(eid)
            if first_run or not matches(entry, feed.get("keywords")):
                continue  # first run only records a baseline
            if posted >= MAX_POSTS_PER_RUN:
                skipped += 1
                continue
            icon = EMOJI.get(feed.get("category"), "📰")
            notify(f"{icon} **{name}**: {entry.get('title', '(no title)')}\n{entry.get('link', '')}")
            posted += 1
        seen[name] = ids[-KEEP_IDS:]

    if skipped:
        notify(f"…and {skipped} more new items this run (hit the per-run limit).")
    SEEN.write_text(json.dumps(seen, indent=2))
    if first_run:
        print("First run: saved baseline, no alerts sent.")


if __name__ == "__main__":
    sys.exit(main())
