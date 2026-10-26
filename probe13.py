#!/usr/bin/env python3
"""Round 4: Google News site: search with a colon-safe query for Swarajya / PTI."""
import json
import re
import urllib.parse
import urllib.request

import feedparser

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")


def get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "application/rss+xml, application/xml, */*"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.status, r.read()


def gn(q, lang="en-in"):
    m = {"en-au": ("en-AU", "AU", "AU:en"), "en-in": ("en-IN", "IN", "IN:en")}
    hl, gl, ceid = m[lang]
    # keep ':' unescaped - Google rejects %3A in this position
    return ("https://news.google.com/rss/search" + urllib.parse.quote(q, safe=":")
            + "&hl=" + hl + "&gl=" + gl + "&ceid=" + ceid)


out = {}
for label, q in (("swarajya", "site:swarajyamag.com"),
                 ("pti", "site:ptinews.com"),
                 ("ani", "site:aninews.in")):
    rec = {}
    try:
        st, raw = get(gn(q))
        d = feedparser.parse(raw)
        rec["status"] = st
        rec["entries"] = len(d.entries)
        if d.entries:
            e = d.entries[0]
            rec["title"] = (e.get("title", "") or "")[:70]
            rec["keys"] = sorted(e.keys())[:14]
            rec["source"] = (e.get("source") if isinstance(e.get("source"), dict) else {})
            desc = e.get("summary", "") or ""
            rec["desc"] = desc[:300]
            rec["desc_has_publisher_link"] = bool(
                re.search(r"swarajyamag\.com|ptinews\.com|aninews\.in", desc))
    except Exception as ex:
        rec["error"] = type(ex).__name__ + ": " + str(ex)[:80]
    out[label] = rec
    print(label, "->", json.dumps(rec)[:400])

# a couple of last-chance Swarajya patterns
extra = ["https://swarajyamag.com/rss/feed/category/national.xml",
         "https://swarajyamag.com/rss/feed/category/economy.xml",
         "https://swarajyamag.com/news/feed",
         "https://swarajyamag.com/feed/economy"]
res = {}
for u in extra:
    try:
        st, raw = get(u)
        d = feedparser.parse(raw)
        res[u] = {"status": st, "entries": len(d.entries),
                  "sample": (d.entries[0].get("title", "") or "")[:50] if d.entries else ""}
    except Exception as ex:
        res[u] = {"error": type(ex).__name__ + ": " + str(ex)[:50]}
out["swarajya_extra"] = res
for u, v in res.items():
    print("  ", v, u[:66])

json.dump(out, open("probe13.json", "w"), indent=1)
