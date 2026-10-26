#!/usr/bin/env python3
"""Probe Swarajya / PTI / ANI feeds."""
import json
import re
import urllib.request

import feedparser

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")

FEEDS = [
    "https://swarajyamag.com/feed",
    "https://swarajyamag.com/rss",
    "https://swarajyamag.com/feed/",
    "https://swarajyamag.com/business/feed",
    "https://swarajyamag.com/economy/feed",
    "https://swarajyamag.com/india/feed",
    "https://www.ptinews.com/rss",
    "https://www.ptinews.com/rss/national",
    "https://www.ptinews.com/feed",
    "https://www.ptinews.com/rss/business",
    "https://ptinews.com/rss",
    "https://www.aninews.in/rss/",
    "https://www.aninews.in/rss/national/",
    "https://www.aninews.in/rss/business/",
    "https://aninews.in/feed",
    "https://www.aninews.in/rss/general/",
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
            if e.get("media_content") or e.get("media_thumbnail") or e.get("enclosures"):
                img += 1
            elif re.search(r"<img", e.get("summary", "") or ""):
                img += 1
        rec["img10"] = img
        if d.entries:
            rec["sample"] = (d.entries[0].get("title", "") or "")[:60]
            link = d.entries[0].get("link", "")
            if link.startswith("http"):
                try:
                    _, art = get(link)
                    rec["text_words"] = words(art.decode("utf-8", "ignore"))
                except Exception as ex:
                    rec["text_words"] = "ERR:" + type(ex).__name__
    except Exception as ex:
        rec["error"] = type(ex).__name__ + ": " + str(ex)[:70]
    out[u] = rec
    print(u[:62], "->", json.dumps(rec)[:150])

json.dump(out, open("probe9.json", "w"), indent=1)
