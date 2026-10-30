#!/usr/bin/env python3
"""Probe Goa / Mangalore / math-temple sources, and check every link in the built editions."""
import json
import re
import urllib.request

import feedparser

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")

FEEDS = [
    # Goa news
    "https://www.navhindtimes.in/feed/",
    "https://www.heraldgoa.in/feed/",
    "https://www.heraldgoa.in/rss",
    "https://www.goanewsonline.com/feed/",
    "https://www.gomantaktimes.com/feed/",
    "https://www.prudentmedia.in/rss",
    # Mangalore / coastal Karnataka
    "https://www.mangalorean.com/feed/",
    "https://www.daijiworld.com/rss/news",
    "https://mangaluru.social/feed",
    # math / temple sites
    "https://chitrapurmath.net/feed/",
    "https://www.chitrapurmath.net/feed/",
    "https://kashimath.org/feed/",
    "https://www.kashimath.org/feed/",
    "https://partagalimath.org/feed/",
    "https://www.partagalimath.org/feed/",
    "https://shreeshantadurga.com/feed/",
    "https://shrimangesh.com/feed/",
]


def get(url, accept="application/rss+xml, application/xml, text/html, */*"):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


out = {"feeds": {}, "links": {}}
for u in FEEDS:
    rec = {}
    try:
        d = feedparser.parse(get(u))
        rec["entries"] = len(d.entries)
        if d.entries:
            rec["sample"] = (d.entries[0].get("title", "") or "")[:50]
    except Exception as ex:
        rec["error"] = type(ex).__name__ + ": " + str(ex)[:40]
    out["feeds"][u] = rec
    print(f"n={rec.get('entries',0):3d} {u[:62]}")

# ---- link check across the published editions ----
def check(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA}, method="GET")
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        return type(e).__name__


def links_of(obj):
    found = []
    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k == "link" and isinstance(v, str) and v.startswith("http"):
                    found.append(v)
                else:
                    walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(obj)
    return found


for f in ("pulse.json", "pulse-mr.json", "pulse-kok.json", "spark/edition.json"):
    try:
        data = json.load(open(f, encoding="utf-8"))
    except Exception:
        continue
    ls = sorted(set(links_of(data)))
    bad = {}
    for u in ls:
        st = check(u)
        if st != 200:
            bad[u] = st
    out["links"][f] = {"total": len(ls), "bad": bad}
    print(f"LINKS {f}: {len(ls)} unique, {len(bad)} not 200")

json.dump(out, open("probe20.json", "w"), indent=1)
