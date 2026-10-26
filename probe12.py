#!/usr/bin/env python3
"""Round 3: ANI category feeds from its index, plus more Swarajya/PTI patterns."""
import json
import re
import urllib.parse
import urllib.request

import feedparser

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")


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

# pull every rss link ANI advertises
try:
    _, raw = get("https://www.aninews.in/rss-feed/")
    txt = raw.decode("utf-8", "ignore")
    links = re.findall(r'href=["\']([^"\']+)["\']', txt)
    feeds = [urllib.parse.urljoin("https://www.aninews.in/rss-feed/", l)
             for l in links if "rss" in l.lower() or l.endswith(".xml")]
    seen, uniq = set(), []
    for f in feeds:
        if f not in seen:
            seen.add(f)
            uniq.append(f)
    out["ani_advertised"] = uniq[:12]
except Exception as e:
    out["ani_advertised"] = {"error": str(e)[:80]}

CANDS = (out.get("ani_advertised") if isinstance(out.get("ani_advertised"), list) else []) + [
    "https://www.aninews.in/rss/feed/category/national.xml",
    "https://www.aninews.in/rss/feed/category/business.xml",
    "https://www.aninews.in/rss/feed/category/world.xml",
    "https://www.aninews.in/rss/feed/category/top.xml",
    "https://swarajyamag.com/api/rss",
    "https://swarajyamag.com/feed/rss",
    "https://swarajyamag.com/rssfeed",
    "https://swarajyamag.com/feed/all",
    "https://www.ptinews.com/rss/feed/category/national.xml",
    "https://www.ptinews.com/rssfeed",
]

results = {}
for u in CANDS:
    rec = {}
    try:
        st, raw = get(u)
        d = feedparser.parse(raw)
        rec["status"] = st
        rec["entries"] = len(d.entries)
        img = 0
        for e in d.entries[:10]:
            if e.get("media_content") or e.get("media_thumbnail") or e.get("enclosures") \
                    or re.search(r"<img", e.get("summary", "") or ""):
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
        rec["error"] = type(ex).__name__ + ": " + str(ex)[:60]
    results[u] = rec

out["results"] = results
json.dump(out, open("probe12.json", "w"), indent=1)
print("ANI advertised:", json.dumps(out["ani_advertised"])[:400])
for u, v in results.items():
    print(f"  n={v.get('entries',0):3d} img={v.get('img10',0):2d} txt={str(v.get('text_words')):>5s} {u[:74]}")
