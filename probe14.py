#!/usr/bin/env python3
"""Probe Marathi-language and Konkani-community feeds."""
import json
import re
import urllib.parse
import urllib.request

import feedparser

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")

FEEDS = [
    # Marathi newspapers / TV
    "https://www.loksatta.com/feed/",
    "https://www.loksatta.com/rss",
    "https://www.lokmat.com/feed/",
    "https://www.lokmat.com/rss",
    "https://www.esakal.com/rss",
    "https://www.esakal.com/feed",
    "https://divyamarathi.com/rss",
    "https://divyamarathi.com/feed",
    "https://marathi.abplive.com/rss",
    "https://marathi.abplive.com/feed",
    "https://www.pudhari.co.in/rss",
    "https://www.maharashtratimes.com/rssfeeds/default.aspx",
    "https://maharashtratimes.com/rssfeeds/-2128936835.cms",
    "https://zeenews.india.com/marathi/rss",
    "https://lokmat.news18.com/rss",
    # Konkani / Mangalore-Konkani community
    "https://www.daijiworld.com/rss",
    "https://www.daijiworld.com/news/rss",
    "https://www.mangalorean.com/feed/",
    "https://konkaniworld.com/feed",
    "https://www.konkaniworld.com/rss",
]


def get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/html, */*"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.status, r.read()


def words(html):
    txt = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    ps = re.findall(r"(?is)<p[^>]*>(.*?)</p>", txt)
    return len(" ".join(re.sub(r"<[^>]+>", " ", p) for p in ps).split())


out = {}
for u in FEEDS:
    rec = {}
    try:
        st, raw = get(u)
        rec["status"] = st
        d = feedparser.parse(raw)
        rec["entries"] = len(d.entries)
        img = 0
        for e in d.entries[:10]:
            if e.get("media_content") or e.get("media_thumbnail") or e.get("enclosures") \
                    or re.search(r"<img", e.get("summary", "") or ""):
                img += 1
        rec["img10"] = img
        if d.entries:
            t = d.entries[0].get("title", "") or ""
            rec["sample"] = t[:60]
            rec["devanagari"] = bool(re.search(r"[\u0900-\u097F]", t))
            link = d.entries[0].get("link", "")
            if link.startswith("http"):
                try:
                    _, art = get(link)
                    rec["text_words"] = words(art.decode("utf-8", "ignore"))
                except Exception as ex:
                    rec["text_words"] = "ERR:" + type(ex).__name__
    except Exception as ex:
        rec["error"] = type(ex).__name__ + ": " + str(ex)[:60]
    out[u] = rec
    print(f"n={rec.get('entries',0):3d} dev={str(rec.get('devanagari')):5s} img={rec.get('img10',0):2d} "
          f"txt={str(rec.get('text_words')):>5s} {u[:56]}")

json.dump(out, open("probe14.json", "w"), indent=1)
