#!/usr/bin/env python3
"""Pulse feed builder.

Fetches public RSS/Atom feeds, normalises them, and writes feed.json
(next to index.html) so the web app can read news same-origin with no
CORS proxy. Runs on GitHub Actions on a schedule.
"""
import calendar
import html
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import feedparser

UA = "Mozilla/5.0 (compatible; PulseBot/1.0; +https://github.com/akshaybangalorekar/pulse)"
PER_KEY = 40
TIMEOUT = 20


def gn(q, lang):
    """Google News RSS search URL for a query in a given locale."""
    m = {"en-au": ("en-AU", "AU", "AU:en"),
         "en-in": ("en-IN", "IN", "IN:en"),
         "hi":    ("hi-IN", "IN", "IN:hi"),
         "mr":    ("mr-IN", "IN", "IN:mr")}
    hl, gl, ceid = m.get(lang, m["en-au"])
    return "https://news.google.com/rss/search?q=%s&hl=%s&gl=%s&ceid=%s" % (
        urllib.parse.quote(q), hl, gl, ceid)


# ---- feed catalogue ----------------------------------------------------
def india(l):
    f = [gn("Indian economy", "en-in"), gn("India rupee GDP markets", "en-in"),
         "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
         "https://www.thehindu.com/business/feeder/default.rss"]
    if l == "hi":
        f.append(gn("भारतीय अर्थव्यवस्था", "hi"))
    if l == "mr":
        f.append(gn("भारतीय अर्थव्यवस्था", "mr"))
    return f


def movies(l):
    f = [gn("upcoming movie releases Australia", "en-au"),
         gn("upcoming Hindi film release", "en-in"),
         "https://www.bollywoodhungama.com/feed/"]
    if l == "mr":
        f.append(gn("मराठी चित्रपट", "mr"))
    return f


CATALOG = {
    "top": lambda l: [gn("Australia news", "en-au"), gn("Melbourne news", "en-au"),
                      gn("India news", "en-in")],
    "australia": lambda l: [gn("Australian economy", "en-au"),
                            gn("RBA interest rates Australia", "en-au"),
                            gn("Australia jobs inflation wages", "en-au"),
                            "https://www.abc.net.au/news/feed/51892/rss.xml",
                            "https://www.rba.gov.au/rss/rss-cb-media-releases.xml"],
    "india": india,
    "sports|all": lambda l: [gn("cricket", "en-au"), gn("tennis ATP WTA", "en-au"),
                             gn("football soccer", "en-au"), gn("basketball NBA NBL", "en-au"),
                             "https://www.espncricinfo.com/rss/content/story/feeds/0.xml",
                             "https://feeds.bbci.co.uk/sport/rss.xml"],
    "sports|cricket": lambda l: [gn("cricket", "en-au"),
                                 "https://www.espncricinfo.com/rss/content/story/feeds/0.xml",
                                 "https://www.cricbuzz.com/rss-feed/cricket-news/"],
    "sports|tennis": lambda l: [gn("tennis ATP WTA", "en-au"),
                                "https://www.atptour.com/en/media/rss-feed/xmlfeed.xml"],
    "sports|football": lambda l: [gn("football soccer", "en-au"),
                                  "https://feeds.bbci.co.uk/sport/football/rss.xml"],
    "sports|basketball": lambda l: [gn("basketball NBA NBL", "en-au"),
                                    "https://www.espn.com/espn/rss/nba/news"],
    "melbourne": lambda l: ["https://www.timeout.com/melbourne/feed/all.rss",
                            "https://www.broadsheet.com.au/melbourne/feed",
                            "https://beat.com.au/feed/",
                            gn("Melbourne events this weekend", "en-au"),
                            gn("Melbourne live music concerts", "en-au"),
                            gn("Melbourne comedy stand up", "en-au")],
    "kids": lambda l: ["https://feeds.bbci.co.uk/newsround/rss.xml",
                       "https://www.dogonews.com/feed",
                       gn("good news stories kids", "en-au"),
                       gn("space animals discovery kids", "en-au")],
    "tech": lambda l: ["https://www.snexplores.org/feed",
                       "https://feeds.bbci.co.uk/news/technology/rss.xml",
                       gn("artificial intelligence explained", "en-au"),
                       gn("quantum computing breakthrough", "en-au"),
                       gn("biotechnology discovery health", "en-au")],
    "study": lambda l: [gn("STEM subjects students Australia", "en-au"),
                        gn("most popular university courses Australia", "en-au"),
                        gn("India students engineering medicine trend", "en-in"),
                        gn("study trends students India Australia", "en-au")],
    "movies": movies,
    "books": lambda l: [gn("books for 11 year olds Australia", "en-au"),
                        gn("children's book awards Australia", "en-au"),
                        gn("best books for tweens", "en-au")],
    "major": lambda l: [gn("Olympics", "en-au"), gn("Commonwealth Games", "en-au"),
                        gn("Formula 1 Australian Grand Prix Melbourne", "en-au"),
                        gn("world championships sport", "en-au"),
                        "https://feeds.bbci.co.uk/sport/rss.xml"],
}
# keys that need a separate copy per language
LANG_KEYS = {"india", "movies"}


# ---- fetch + parse -----------------------------------------------------
def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "application/rss+xml, application/xml, text/xml, */*"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def clean(s):
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s).strip()


def parse(raw):
    d = feedparser.parse(raw)
    out = []
    for e in d.entries:
        title = clean(e.get("title", ""))
        link = e.get("link", "") or ""
        src = ""
        s = e.get("source")
        if isinstance(s, dict):
            src = clean(s.get("title", ""))
        if src and title.endswith(" - " + src):
            title = title[: len(title) - len(src) - 3]
        if not src:
            try:
                src = urllib.parse.urlparse(link).netloc.replace("www.", "")
            except Exception:
                src = ""
        ts = None
        for k in ("published_parsed", "updated_parsed"):
            if e.get(k):
                ts = calendar.timegm(e[k]) * 1000
                break
        if ts is None:
            ts = int(time.time() * 1000)
        img = ""
        for k in ("media_content", "media_thumbnail"):
            v = e.get(k)
            if v and isinstance(v, list) and v[0].get("url"):
                img = v[0]["url"]
                break
        if not img:
            for en in e.get("enclosures", []) or []:
                if en.get("href") and str(en.get("type", "")).startswith("image"):
                    img = en["href"]
                    break
        if title and link:
            out.append({"title": title, "link": link, "source": src,
                        "image": img, "date": ts})
    return out


def gather(urls):
    items, seen = [], set()
    for u in urls:
        try:
            got = parse(fetch(u))
        except Exception as ex:
            print("  ! fail", u, "->", type(ex).__name__, ex)
            continue
        print("  ok", len(got), u)
        for it in got:
            k = it["title"].lower()
            if k in seen:
                continue
            seen.add(k)
            items.append(it)
    items.sort(key=lambda x: x["date"], reverse=True)
    return items[:PER_KEY]


def main():
    data = {}
    for key, fn in CATALOG.items():
        langs = ["en", "hi", "mr"] if key in LANG_KEYS else ["en"]
        for l in langs:
            print("KEY", key, l)
            items = gather(fn(l))
            if len(langs) == 1:
                data[key] = items
            else:
                data[key + "|" + l] = items
    out = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "data": data}
    with open("feed.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    n = sum(len(v) for v in data.values())
    print("WROTE feed.json:", n, "items across", len(data), "keys")


if __name__ == "__main__":
    main()
