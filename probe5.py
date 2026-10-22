#!/usr/bin/env python3
"""Find tennis-analysis, coaching, football/basketball and age-appropriate screen sources."""
import json
import re
import urllib.parse
import urllib.request

import feedparser

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")

FEEDS = [
    "https://www.tennismajors.com/feed/",
    "https://www.tennisnow.com/rss",
    "https://www.tennis.com/feed",
    "https://tennishead.net/feed/",
    "https://www.ubitennis.net/feed/",
    "https://lastwordonsports.com/tennis/feed/",
    "https://www.tennisworldusa.org/rss/news/1/tennis-news.xml",
    "https://hoopshype.com/feed/",
    "https://www.slamonline.com/feed/",
    "https://basketball.realgm.com/rss/news.xml",
    "https://www.eurohoops.net/feed/",
    "https://www.espn.com/espn/rss/soccer/news",
    "https://www.goal.com/feeds/en/news",
    "https://www.animationmagazine.net/feed/",
    "https://kidscreen.com/feed/",
    "https://www.dogonews.com/feed",
]
GN = [
    "tennis analysis", "tennis technique tips", "how to improve tennis forehand",
    "tennis coaching drills", "junior tennis training", "tennis match analysis",
    "football tactics analysis", "basketball tactics analysis",
    "kids movie release", "new animated family film",
]


def gn(q, lang="en-au"):
    m = {"en-au": ("en-AU", "AU", "AU:en"), "en-in": ("en-IN", "IN", "IN:en")}
    hl, gl, ceid = m[lang]
    return ("https://news.google.com/rss/search" + urllib.parse.quote(q)
            + "&hl=" + hl + "&gl=" + gl + "&ceid=" + ceid)


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


out = {"feeds": {}, "gn": {}}
for u in FEEDS:
    try:
        st, raw = get(u)
        d = feedparser.parse(raw)
        n = len(d.entries)
        rec = {"status": st, "entries": n,
               "with_image": sum(1 for e in d.entries if img_of(e)),
               "sample": (d.entries[0].get("title", "")[:58] if n else "")}
        if n:
            rec["text_words"] = text_words(d.entries[0].get("link", ""))
        out["feeds"][u] = rec
    except Exception as e:
        out["feeds"][u] = {"error": type(e).__name__ + ": " + str(e)[:60]}

for q in GN:
    try:
        st, raw = get(gn(q))
        d = feedparser.parse(raw)
        out["gn"][q] = {"entries": len(d.entries),
                        "sample": (d.entries[0].get("title", "")[:70] if d.entries else "")}
    except Exception as e:
        out["gn"][q] = {"error": type(e).__name__ + ": " + str(e)[:60]}

json.dump(out, open("probe5.json", "w"), indent=1)
print(json.dumps(out, indent=1))
