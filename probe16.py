#!/usr/bin/env python3
"""Confirm Marathi feeds and check article-text extraction."""
import json
import re
import urllib.request

import feedparser

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")

FEEDS = [
    "https://maharashtratimes.com/sitemap/rssfeed.xml",
    "https://maharashtratimes.com/langapi/sitemap/gstandrssfeed.xml",
    "https://divyamarathi.com/rss",
    "https://www.lokmat.com/rss/news",
    "https://marathi.abplive.com/rss/news",
    "https://www.esakal.com/rss/news",
    "https://www.loksatta.com/rss/news",
    "https://www.daijiworld.com/common/commonPage",
    "https://www.mangalorean.com/feed/",
]


def get(url, accept="application/rss+xml, application/xml, text/html, */*"):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.status, r.read()


def article_words(url):
    try:
        st, raw = get(url, "text/html,*/*")
        txt = raw.decode("utf-8", "ignore")
        txt = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", txt)
        ps = re.findall(r"(?is)<p[^>]*>(.*?)</p>", txt)
        body = " ".join(re.sub(r"<[^>]+>", " ", p) for p in ps)
        return len(body.split())
    except Exception as ex:
        return "ERR:" + type(ex).__name__


out = {}
for u in FEEDS:
    rec = {}
    try:
        st, raw = get(u)
        d = feedparser.parse(raw)
        rec["status"] = st
        rec["entries"] = len(d.entries)
        dev = sum(1 for e in d.entries[:10]
                  if re.search(r"[\u0900-\u097F]", e.get("title", "") or ""))
        rec["devanagari_of_10"] = dev
        img = sum(1 for e in d.entries[:10]
                  if e.get("media_content") or e.get("media_thumbnail")
                  or e.get("enclosures") or re.search(r"<img", e.get("summary", "") or ""))
        rec["img_of_10"] = img
        if d.entries:
            rec["sample"] = (d.entries[0].get("title", "") or "")[:55]
            link = d.entries[0].get("link", "")
            if link.startswith("http"):
                rec["text_words"] = article_words(link)
    except Exception as ex:
        rec["error"] = type(ex).__name__ + ": " + str(ex)[:55]
    out[u] = rec
    print(f"n={rec.get('entries',0):3d} dev10={rec.get('devanagari_of_10',0):2d} img10={rec.get('img_of_10',0):2d} "
          f"txt={str(rec.get('text_words')):>6s} {u[:58]}")

json.dump(out, open("probe16.json", "w"), indent=1)
