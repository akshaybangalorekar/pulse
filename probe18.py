#!/usr/bin/env python3
"""Probe Konkani (daijiworld, thegoan) and Marathi magazine sources."""
import json
import re
import urllib.request

import feedparser

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")

FEEDS = [
    # Konkani / Mangalore
    "https://www.daijiworld.com/rssfeed",
    "https://www.daijiworld.com/rss/news.xml",
    "https://www.daijiworld.com/common/commonPage",
    "https://www.daijiworld.com/news/newsfeed",
    "https://thegoan.net/feed/",
    "https://www.thegoan.net/feed/",
    "https://thegoan.net/rss",
    "https://www.thegoan.net/rss",
    "https://epaper.thegoan.net/rss",
    # Marathi magazines / culture
    "https://chitralekha.com/feed",
    "https://www.chitralekha.com/feed/",
    "https://lokprabha.com/feed",
    "https://www.mahermarathi.com/feed",
    "https://divyamarathi.com/rss",
]


def get(url, accept="application/rss+xml, application/xml, text/html, */*"):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()


def words(html):
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    ps = re.findall(r"(?is)<p[^>]*>(.*?)</p>", t)
    return len(" ".join(re.sub(r"<[^>]+>", " ", p) for p in ps).split())


out = {}
for u in FEEDS:
    rec = {}
    try:
        raw = get(u)
        d = feedparser.parse(raw)
        rec["entries"] = len(d.entries)
        if d.entries:
            rec["sample"] = (d.entries[0].get("title", "") or "")[:55]
            link = d.entries[0].get("link", "")
            rec["link"] = link[:90]
            if link.startswith("http"):
                try:
                    page = get(link, "text/html,*/*").decode("utf-8", "ignore")
                    rec["text_words"] = words(page)
                    og = re.search(r'property=["\']og:image["\'][^>]*content=["\']([^"\']+)', page)
                    rec["og_image"] = bool(og)
                except Exception as ex:
                    rec["text_words"] = "ERR:" + type(ex).__name__
    except Exception as ex:
        rec["error"] = type(ex).__name__ + ": " + str(ex)[:50]
    out[u] = rec
    print(f"n={rec.get('entries',0):3d} txt={str(rec.get('text_words')):>6s} og={str(rec.get('og_image')):5s} {u[:62]}")

json.dump(out, open("probe18.json", "w"), indent=1)
