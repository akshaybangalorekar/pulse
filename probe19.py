#!/usr/bin/env python3
"""Check the seen-memory state and probe kids' current-affairs feeds."""
import json
import os
import re
import urllib.request

import feedparser

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")

FEEDS = [
    "https://feeds.bbci.co.uk/newsround/rss.xml",
    "https://www.abc.net.au/news/feed/51120/rss.xml",
    "https://www.abc.net.au/news/feed/45910/rss.xml",
    "https://www.sciencejournalforkids.org/feed/",
    "https://www.smithsonianmag.com/rss/latest_articles/",
    "https://www.newscientist.com/feed/home/",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.thehindu.com/sci-tech/feeder/default.rss",
    "https://indianexpress.com/section/technology/feed/",
]

out = {"seen": {}, "feeds": {}}
for f in ("pulse-seen.json", "spark-seen.json"):
    try:
        d = json.load(open(f))
        out["seen"][f] = {"count": len(d), "sample": list(d.keys())[:4]}
    except Exception as e:
        out["seen"][f] = {"error": type(e).__name__}

for u in FEEDS:
    rec = {}
    try:
        req = urllib.request.Request(u, headers={"User-Agent": UA,
                                                 "Accept": "application/rss+xml, application/xml, */*"})
        with urllib.request.urlopen(req, timeout=25) as r:
            d = feedparser.parse(r.read())
        rec["entries"] = len(d.entries)
        if d.entries:
            rec["sample"] = (d.entries[0].get("title", "") or "")[:55]
    except Exception as ex:
        rec["error"] = type(ex).__name__ + ": " + str(ex)[:50]
    out["feeds"][u] = rec
    print(f"n={rec.get('entries',0):3d} {u[:60]}")

print("SEEN:", json.dumps(out["seen"])[:300])
json.dump(out, open("probe19.json", "w"), indent=1)
