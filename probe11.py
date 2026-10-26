#!/usr/bin/env python3
"""Round 2: inspect ANI's rss-feed index, try more patterns, and check Google News site: as a fallback."""
import json
import re
import urllib.parse
import urllib.request

import feedparser

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")


def get(url, accept="application/rss+xml, application/xml, text/html, */*"):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.status, r.read()


out = {}

# 1. what is ANI's rss-feed index?
try:
    st, raw = get("https://www.aninews.in/rss-feed/")
    txt = raw.decode("utf-8", "ignore")
    links = re.findall(r'href=["\']([^"\']*rss[^"\']*)["\']', txt, re.I)
    out["ani_index"] = {"status": st, "len": len(txt), "head": txt[:300], "links": links[:20]}
except Exception as e:
    out["ani_index"] = {"error": str(e)[:100]}

# 2. more candidate feed URLs
CANDS = [
    "https://swarajyamag.com/rss.xml",
    "https://swarajyamag.com/feed.xml",
    "https://swarajyamag.com/feeds",
    "https://swarajyamag.com/rss/all",
    "https://www.ptinews.com/rss.xml",
    "https://www.ptinews.com/feeds",
    "https://www.aninews.in/rss-feed/national/",
    "https://www.aninews.in/rss-feed/business/",
    "https://www.aninews.in/rss-feed/world/",
    "https://www.aninews.in/rss-feed/india/",
]
for u in CANDS:
    try:
        st, raw = get(u)
        d = feedparser.parse(raw)
        out[u] = {"status": st, "entries": len(d.entries),
                  "sample": (d.entries[0].get("title", "") or "")[:60] if d.entries else ""}
    except Exception as e:
        out[u] = {"error": type(e).__name__ + ": " + str(e)[:60]}

# 3. Google News site: fallback - can we recover the publisher URL from an item?
def gn(q, lang="en-in"):
    m = {"en-au": ("en-AU", "AU", "AU:en"), "en-in": ("en-IN", "IN", "IN:en")}
    hl, gl, ceid = m[lang]
    return ("https://news.google.com/rss/search" + urllib.parse.quote(q)
            + "&hl=" + hl + "&gl=" + gl + "&ceid=" + ceid)


for site in ("site:aninews.in", "site:ptinews.com", "site:swarajyamag.com"):
    try:
        st, raw = get(gn(site))
        d = feedparser.parse(raw)
        rec = {"status": st, "entries": len(d.entries)}
        if d.entries:
            e = d.entries[0]
            rec["title"] = (e.get("title", "") or "")[:60]
            rec["link"] = (e.get("link", "") or "")[:120]
            src = e.get("source")
            rec["source_attr"] = (src.get("href", "") if isinstance(src, dict) else "")[:100]
            desc = e.get("summary", "") or ""
            rec["desc_head"] = desc[:220]
        out[site] = rec
    except Exception as ex:
        out[site] = {"error": type(ex).__name__ + ": " + str(ex)[:70]}

json.dump(out, open("probe11.json", "w"), indent=1)
for k, v in out.items():
    print(k[:64], "->", json.dumps(v)[:230])
