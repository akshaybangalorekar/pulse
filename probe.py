#!/usr/bin/env python3
"""One-off probe: which publisher feeds work, and which carry images."""
import json
import re
import urllib.request

import feedparser

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

FEEDS = {
    "newsround":   "https://feeds.bbci.co.uk/newsround/rss.xml",
    "dogonews":    "https://www.dogonews.com/feed",
    "snexplores":  "https://www.snexplores.org/feed",
    "nasa":        "https://www.nasa.gov/rss/dyn/breaking_news.rss",
    "verge":       "https://www.theverge.com/rss/index.xml",
    "abc_top":     "https://www.abc.net.au/news/feed/51120/rss.xml",
    "abc_business":"https://www.abc.net.au/news/feed/51892/rss.xml",
    "guardian_au": "https://www.theguardian.com/au/rss",
    "guardian_world": "https://www.theguardian.com/world/rss",
    "cricinfo":    "https://www.espncricinfo.com/rss/content/story/feeds/0.xml",
    "atp":         "https://www.atptour.com/en/media/rss-feed/xmlfeed.xml",
    "timeout_mel": "https://www.timeout.com/melbourne/feed/all.rss",
    "broadsheet":  "https://www.broadsheet.com.au/melbourne/feed",
    "bbc_sport":   "https://feeds.bbci.co.uk/sport/rss.xml",
    "bbc_tech":    "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "bollywood":   "https://www.bollywoodhungama.com/feed/",
    "ausgeo":      "https://www.australiangeographic.com.au/feed/",
    "smithsonian": "https://www.smithsonianmag.com/rss/latest/",
    "physorg":     "https://phys.org/rss-feed/",
    "spacecom":    "https://www.space.com/feeds/all",
    "bbcscience":  "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
    "natgeo":      "https://www.nationalgeographic.com/rss/feed",
    "cnet":        "https://www.cnet.com/rss/news/",
    "ign":         "https://feeds.ign.com/ign/all",
}


def fetch(u):
    req = urllib.request.Request(u, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def img_of(e):
    for k in ("media_content", "media_thumbnail"):
        v = e.get(k)
        if v and isinstance(v, list) and v[0].get("url"):
            return v[0]["url"]
    for en in e.get("enclosures", []) or []:
        if en.get("href"):
            return en["href"]
    for f in ("summary", "description"):
        d = e.get(f, "") or ""
        m = re.search(r'<img[^>]+src=["\']([^"\']+)', d)
        if m:
            return m.group(1)
    return ""


out = {}
for name, u in FEEDS.items():
    try:
        d = feedparser.parse(fetch(u))
        n = len(d.entries)
        w = sum(1 for e in d.entries if img_of(e))
        out[name] = {"url": u, "items": n, "with_image": w,
                     "sample_title": (d.entries[0].get("title", "")[:60] if n else ""),
                     "sample_img": (img_of(d.entries[0])[:110] if n else "")}
    except Exception as ex:
        out[name] = {"url": u, "error": type(ex).__name__ + ": " + str(ex)[:90]}

json.dump(out, open("spark/probe.json", "w"), indent=1)
print(json.dumps(out, indent=1))
