#!/usr/bin/env python3
"""One-off probe: which publisher feeds work, and which carry images."""
import json
import re
import urllib.request

import feedparser

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

FEEDS = {
    "hindu_national": "https://www.thehindu.com/news/national/feeder/default.rss",
    "hindu_sport":    "https://www.thehindu.com/sport/feeder/default.rss",
    "toi_top":        "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
    "ndtv":           "https://feeds.feedburner.com/ndtvnews-top-stories",
    "indianexpress":  "https://indianexpress.com/feed/",
    "ht_india":       "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml",
    "espn_nba":       "https://www.espn.com/espn/rss/nba/news",
    "espn_tennis":    "https://www.espn.com/espn/rss/tennis/news",
    "abc_sport":      "https://www.abc.net.au/news/feed/45910/rss.xml",
    "abc_science":    "https://www.abc.net.au/news/feed/10574772/rss.xml",
    "comingsoon":     "https://www.comingsoon.net/feed",
    "variety_film":   "https://variety.com/v/film/feed/",
    "sciencedaily":   "https://www.sciencedaily.com/rss/all.xml",
    "cricket_au":     "https://www.cricket.com.au/news/rss",
    "ign":            "https://feeds.ign.com/ign/all",
    "bbc_entertain":  "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml",
    "natgeo_animals": "https://www.nationalgeographic.com/animals/rss/feed",
    "gizmodo":        "https://gizmodo.com/rss",
    "theverge":       "https://www.theverge.com/rss/index.xml",
    "sciencealert":   "https://www.sciencealert.com/feed",
}


def fetch(u):
    req = urllib.request.Request(u, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def img_of(e):
    for k in ("media_content", "media_thumbnail"):
        v = e.get(k)
        if v and isinstance(v, list) and v[0].get("url"):
            return v[0]["url"]
    for en in e.get("enclosures", []) or []:
        if en.get("href"):
            return en["href"]
    for f in ("summary", "description"):
        d = e.get(f, "") or ""
        m = re.search(r'<img[^>]+src=["\']([^"\']+)', d)
        if m:
            return m.group(1)
    return ""


out = {}
for name, u in FEEDS.items():
    try:
        d = feedparser.parse(fetch(u))
        n = len(d.entries)
        w = sum(1 for e in d.entries if img_of(e))
        out[name] = {"url": u, "items": n, "with_image": w,
                     "sample_title": (d.entries[0].get("title", "")[:60] if n else ""),
                     "sample_img": (img_of(d.entries[0])[:110] if n else "")}
    except Exception as ex:
        out[name] = {"url": u, "error": type(ex).__name__ + ": " + str(ex)[:90]}

json.dump(out, open("spark/probe.json", "w"), indent=1)
print(json.dumps(out, indent=1))
