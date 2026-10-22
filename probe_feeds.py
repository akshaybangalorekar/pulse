#!/usr/bin/env python3
"""Discover working feeds for the kid-news sources + sport/ranking sources."""
import json
import re
import urllib.request

import feedparser

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")

HOMES = {
    "pressgang": "https://pressgang.news/",
    "btn": "https://www.abc.net.au/btn",
    "squiz": "https://www.squizkids.com.au/",
    "kidsnews": "https://www.kidsnews.com.au/",
    "timeforkids": "https://www.timeforkids.com/",
    "tennisaustralia": "https://www.tennis.com.au/news",
    "nbl": "https://nbl.com.au/news",
    "utr": "https://utrsports.net/",
}
CANDIDATES = [
    "https://pressgang.news/feed", "https://pressgang.news/rss", "https://pressgang.news/feed.xml",
    "https://pressgang.news/rss.xml",
    "https://www.abc.net.au/btn/feed", "https://www.abc.net.au/btn/rss.xml",
    "https://www.abc.net.au/news/feed/btn/rss.xml",
    "https://www.squizkids.com.au/feed", "https://www.squizkids.com.au/feed/podcast",
    "https://www.squizkids.com.au/rss",
    "https://www.kidsnews.com.au/rss", "https://www.kidsnews.com.au/feed",
    "https://www.kidsnews.com.au/rss.xml",
    "https://www.timeforkids.com/feed", "https://www.timeforkids.com/rss",
    "https://www.timeforkids.com/feed/",
    "https://www.tennis.com.au/news/feed", "https://www.tennis.com.au/feed",
    "https://nbl.com.au/news/feed", "https://nbl.com.au/feed",
    "https://www.espn.com/espn/rss/nba/news",
    "https://www.atptour.com/en/media/rss-feed/xmlfeed.xml",
]


def get(url, nbytes=200000):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/rss+xml,*/*"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status, r.read(nbytes)


out = {"homes": {}, "candidates": {}}

for name, url in HOMES.items():
    try:
        st, raw = get(url)
        txt = raw.decode("utf-8", "ignore")
        links = re.findall(r'<link[^>]+type=["\']application/rss\+xml["\'][^>]*>', txt, re.I)
        hrefs = []
        for l in links:
            m = re.search(r'href=["\']([^"\']+)', l)
            if m:
                hrefs.append(m.group(1))
        out["homes"][name] = {"url": url, "status": st, "rss_links": hrefs[:4],
                              "has_json_api": bool(re.search(r"/api/|\.json", txt))}
    except Exception as e:
        out["homes"][name] = {"url": url, "error": type(e).__name__ + ": " + str(e)[:80]}

for url in CANDIDATES:
    try:
        st, raw = get(url)
        d = feedparser.parse(raw)
        out["candidates"][url] = {"status": st, "entries": len(d.entries),
                                  "title": (d.feed.get("title", "")[:60] if d.entries else ""),
                                  "sample": (d.entries[0].get("title", "")[:70] if d.entries else "")}
    except Exception as e:
        out["candidates"][url] = {"error": type(e).__name__ + ": " + str(e)[:70]}

json.dump(out, open("probe2.json", "w"), indent=1)
print(json.dumps(out, indent=1))
