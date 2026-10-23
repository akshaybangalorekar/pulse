#!/usr/bin/env python3
"""Probe economy/geopolitics publisher feeds: feed + image + readable article text."""
import json
import re
import urllib.request

import feedparser

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")

FEEDS = [
    "https://economictimes.indiatimes.com/news/economy/rssfeeds/1373380680.cms",
    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "https://www.business-standard.com/rss/economy-policy-10201.rss",
    "https://www.thehindu.com/business/Economy/feeder/default.rss",
    "https://www.thehindu.com/business/feeder/default.rss",
    "https://www.livemint.com/rss/economy",
    "https://www.livemint.com/rss/markets",
    "https://www.moneycontrol.com/rss/economy.xml",
    "https://indianexpress.com/section/business/economy/feed/",
    "https://theprint.in/category/economy/feed/",
    "https://swarajyamag.com/feed",
    "https://www.orfonline.org/feed/",
    "https://www.abc.net.au/news/feed/51120/rss.xml",
    "https://www.theguardian.com/au/business/rss",
    "https://www.theguardian.com/world/rss",
    "https://feeds.bbci.co.uk/news/business/rss.xml",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://www.smh.com.au/rss/business.xml",
    "https://www.firstpost.com/commonfeeds/v1/mfp/rss/economy.xml",
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


def text_words(url):
    try:
        txt = get(url)[1].decode("utf-8", "ignore")
    except Exception as e:
        return "ERR:" + type(e).__name__
    txt = re.sub(r"(?is)<(script|style|noscript|nav|footer|aside)[^>]*>.*?</\1>", " ", txt)
    m = re.search(r"(?is)<article[^>]*>(.*?)</article>", txt)
    body = m.group(1) if m else txt
    ps = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", p)).strip()
          for p in re.findall(r"(?is)<p[^>]*>(.*?)</p>", body)]
    return len(" ".join(p for p in ps if len(p) > 70).split())


out = {}
for u in FEEDS:
    try:
        st, raw = get(u)
        d = feedparser.parse(raw)
        n = len(d.entries)
        rec = {"status": st, "entries": n,
               "with_image": sum(1 for e in d.entries if img_of(e)),
               "sample": (d.entries[0].get("title", "")[:56] if n else "")}
        if n:
            rec["text_words"] = text_words(d.entries[0].get("link", ""))
        out[u] = rec
    except Exception as e:
        out[u] = {"error": type(e).__name__ + ": " + str(e)[:60]}

json.dump(out, open("probe6.json", "w"), indent=1)
print(json.dumps(out, indent=1))
