#!/usr/bin/env python3
"""Which frontier-tech / STEM sources work: feed, images, and readable article text."""
import json
import re
import urllib.request

import feedparser

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")

FEEDS = [
    "https://www.technologyreview.com/feed/",
    "https://spectrum.ieee.org/feeds/feed.rss",
    "https://feeds.arstechnica.com/arstechnica/index",
    "https://www.newscientist.com/feed/home/",
    "https://www.quantamagazine.org/feed/",
    "https://singularityhub.com/feed/",
    "https://techcrunch.com/feed/",
    "https://phys.org/rss-feed/",
    "https://www.sciencedaily.com/rss/all.xml",
    "https://www.wired.com/feed/rss",
    "https://www.engadget.com/rss.xml",
    "https://www.freethink.com/feed",
    "https://www.nature.com/nature.rss",
    "https://www.roboticsbusinessreview.com/feed/",
    "https://spectrum.ieee.org/feeds/topic/robotics.rss",
    "https://www.technologyreview.com/topic/artificial-intelligence/feed/",
]


def get(url, nbytes=400000):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status, r.read(nbytes)


def img_of(e):
    for k in ("media_content", "media_thumbnail"):
        v = e.get(k)
        if v and isinstance(v, list) and v[0].get("url"):
            return v[0]["url"]
    for en in e.get("enclosures", []) or []:
        if en.get("href"):
            return en["href"]
    m = re.search(r'<img[^>]+src=["\']([^"\']+)', e.get("summary", "") or "")
    return m.group(1) if m else ""


def text_len(url):
    try:
        txt = get(url, 400000)[1].decode("utf-8", "ignore")
    except Exception as e:
        return "ERR:" + type(e).__name__
    txt = re.sub(r"(?is)<(script|style|noscript|nav|footer|aside)[^>]*>.*?</\1>", " ", txt)
    m = re.search(r"(?is)<article[^>]*>(.*?)</article>", txt)
    body = m.group(1) if m else txt
    ps = [re.sub(r"<[^>]+>", " ", p) for p in re.findall(r"(?is)<p[^>]*>(.*?)</p>", body)]
    ps = [re.sub(r"\s+", " ", p).strip() for p in ps]
    ps = [p for p in ps if len(p) > 70]
    return len(" ".join(ps).split())


out = {}
for u in FEEDS:
    try:
        st, raw = get(u)
        d = feedparser.parse(raw)
        n = len(d.entries)
        w = sum(1 for e in d.entries if img_of(e))
        rec = {"status": st, "entries": n, "with_image": w,
               "sample": (d.entries[0].get("title", "")[:60] if n else "")}
        if n:
            rec["first_link"] = d.entries[0].get("link", "")
            rec["first_text_words"] = text_len(d.entries[0].get("link", ""))
        out[u] = rec
    except Exception as e:
        out[u] = {"error": type(e).__name__ + ": " + str(e)[:70]}

json.dump(out, open("probe4.json", "w"), indent=1)
print(json.dumps(out, indent=1))
