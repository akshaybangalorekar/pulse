#!/usr/bin/env python3
"""Probe centre-right / business / nationalist-leaning Indian and Australian feeds."""
import json
import re
import urllib.request

import feedparser

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")

FEEDS = [
    # India - centre-right / business / reform
    "https://swarajyamag.com/feed",
    "https://theprint.in/category/economy/feed/",
    "https://theprint.in/feed/",
    "https://www.financialexpress.com/feed/",
    "https://www.firstpost.com/rss/business.xml",
    "https://www.firstpost.com/rss/india.xml",
    "https://economictimes.indiatimes.com/news/economy/rssfeeds/1373380680.cms",
    "https://economictimes.indiatimes.com/industry/rssfeeds/13352306.cms",
    "https://www.livemint.com/rss/economy",
    "https://organiser.org/feed/",
    "https://www.orfonline.org/feed/",
    # Australia - centre-right / business
    "https://www.news.com.au/content-feeds/latest-news-national/",
    "https://www.skynews.com.au/rss",
    "https://www.theaustralian.com.au/feed/",
    "https://www.afr.com/rss",
    "https://www.dailytelegraph.com.au/feed/",
    "https://www.smh.com.au/rss/business.xml",
    "https://www.spectator.com.au/feed/",
    "https://www.macrobusiness.com.au/feed/",
]


def get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/html, */*"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.status, r.read()


def words(html):
    txt = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    ps = re.findall(r"(?is)<p[^>]*>(.*?)</p>", txt)
    body = " ".join(re.sub(r"<[^>]+>", " ", p) for p in ps)
    return len(body.split())


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
            elif re.search(r'<img', e.get("summary", "") or ""):
                img += 1
        rec["img10"] = img
        if d.entries:
            link = d.entries[0].get("link", "")
            rec["sample"] = (d.entries[0].get("title", "") or "")[:60]
            if link.startswith("http"):
                try:
                    st2, art = get(link)
                    rec["text_words"] = words(art.decode("utf-8", "ignore"))
                except Exception as ex:
                    rec["text_words"] = "ERR:" + type(ex).__name__
    except Exception as ex:
        rec["error"] = type(ex).__name__ + ": " + str(ex)[:80]
    out[u] = rec
    print(u[:78], "->", json.dumps(rec)[:170])

json.dump(out, open("probe8.json", "w"), indent=1)
