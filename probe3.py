#!/usr/bin/env python3
"""Round 2: more feed patterns + Google News site/query probes for kids' sources and junior sport."""
import json
import urllib.parse
import urllib.request

import feedparser

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")

FEEDS = [
    "https://www.squizkids.com.au/feed/podcast/", "https://www.squizkids.com.au/news/feed",
    "https://www.squizkids.com.au/category/news/feed", "https://www.squizkids.com.au/blog/feed",
    "https://www.squizkids.com.au/feed/",
    "https://www.abc.net.au/btn/rss", "https://www.abc.net.au/btn/feed.xml",
    "https://www.abc.net.au/btn/",
    "https://www.kidsnews.com.au/rss/", "https://www.kidsnews.com.au/feed/",
    "https://www.tennis.com.au/news/rss", "https://www.tennis.com.au/rss",
    "https://www.timeforkids.com/feed/",
]
GN = [
    "site:kidsnews.com.au", "site:squizkids.com.au", "site:pressgang.news",
    "site:timeforkids.com", "site:abc.net.au/btn",
    "Australian junior tennis champion", "junior tennis ranking Australia",
    "under 12 basketball Australia", "junior basketball Australia",
    "India junior tennis champion", "India under-14 basketball",
]


def gn(q, lang="en-au"):
    m = {"en-au": ("en-AU", "AU", "AU:en"), "en-in": ("en-IN", "IN", "IN:en")}
    hl, gl, ceid = m[lang]
    return "https://news.google.com/rss/search" % (
        urllib.parse.quote(q), hl, gl, ceid)


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status, r.read(300000)


out = {"feeds": {}, "gn": {}}
for u in FEEDS:
    try:
        st, raw = get(u)
        d = feedparser.parse(raw)
        out["feeds"][u] = {"status": st, "entries": len(d.entries),
                           "sample": (d.entries[0].get("title", "")[:60] if d.entries else "")}
    except Exception as e:
        out["feeds"][u] = {"error": type(e).__name__ + ": " + str(e)[:60]}

for q in GN:
    for lang in (["en-in"] if "India" in q else ["en-au"]):
        key = q + " [" + lang + "]"
        try:
            st, raw = get(gn(q, lang))
            d = feedparser.parse(raw)
            out["gn"][key] = {"status": st, "entries": len(d.entries),
                              "sample": (d.entries[0].get("title", "")[:70] if d.entries else "")}
        except Exception as e:
            out["gn"][key] = {"error": type(e).__name__ + ": " + str(e)[:60]}

json.dump(out, open("probe3.json", "w"), indent=1)
print(json.dumps(out, indent=1))
