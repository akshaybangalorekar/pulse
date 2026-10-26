#!/usr/bin/env python3
"""Probe Australian and Indian macro / jobs / industry sources."""
import json
import re
import urllib.request

import feedparser

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")

FEEDS = [
    # Australia - official and business
    "https://www.rba.gov.au/rss/rss-cb-media-releases.xml",
    "https://www.rba.gov.au/rss/rss-cb-speeches.xml",
    "https://theconversation.com/au/business/articles.atom",
    "https://theconversation.com/au/topics/employment/articles.atom",
    "https://www.theage.com.au/rss/business.xml",
    "https://www.smh.com.au/rss/business.xml",
    "https://www.abc.net.au/news/feed/51120/rss.xml",
    "https://www.abc.net.au/news/feed/51892/rss.xml",
    "https://www.macrobusiness.com.au/feed/",
    "https://www.spectator.com.au/feed/",
    # India - official
    "https://www.rbi.org.in/pressreleases_rss.xml",
    "https://www.rbi.org.in/Scripts/Rss.aspx",
    "https://pib.gov.in/RssMain.aspx",
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
        img = sum(1 for e in d.entries[:10]
                  if e.get("media_content") or e.get("media_thumbnail") or e.get("enclosures")
                  or re.search(r"<img", e.get("summary", "") or ""))
        rec["img_of_10"] = img
        if d.entries:
            rec["sample"] = (d.entries[0].get("title", "") or "")[:58]
            link = d.entries[0].get("link", "")
            if link.startswith("http"):
                try:
                    rec["text_words"] = words(get(link, "text/html,*/*").decode("utf-8", "ignore"))
                except Exception as ex:
                    rec["text_words"] = "ERR:" + type(ex).__name__
    except Exception as ex:
        rec["error"] = type(ex).__name__ + ": " + str(ex)[:55]
    out[u] = rec
    print(f"n={rec.get('entries',0):3d} img10={rec.get('img_of_10',0):2d} txt={str(rec.get('text_words')):>6s} {u[:64]}")

json.dump(out, open("probe17.json", "w"), indent=1)
