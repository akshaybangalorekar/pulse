#!/usr/bin/env python3
"""Pulse + Spark feed builder.

Fetches public RSS/Atom feeds, normalises them, and writes:
  feed.json            -> Pulse (personal news reader)
  spark/feed.json      -> Spark (kids' news, grouped, real images)
  spark/world.json     -> Spark "in the world" hooks
Runs on GitHub Actions on a schedule; the web apps read these same-origin.
"""
import calendar
import html
import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import feedparser

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
PER_KEY = 40
TIMEOUT = 20

# pirate-stream spam and similar junk that search feeds surface
SPAM = re.compile(r"(live\s*stream|streaming|watch\s+(live|online|free)|free\s*stream|"
                  r"vip\s*stream|soccer\s*stream|reddit\s*stream|\u3010|\u3011|"
                  r"live\s*now|hd\s*stream|full\s*match\s*free)", re.I)
# not for an 11-year-old: violence, crime, sex, war
KID_BLOCK = re.compile(r"\b(kill(?:ed|ing|s)?|dead|death|dies|died|murder(?:ed|s)?|"
                       r"stab(?:bed|bing)?|gunman|shoot(?:ing|ings)?|rape|suicide|"
                       r"overdose|arrest(?:ed|s)?|jail(?:ed)?|prison|war|missile|"
                       r"airstrike|bomb(?:ing|ed|s)?|blast|massacre|hostage|"
                       r"terror(?:ist|ists|ism)?|houthi|nude|porn)\b", re.I)
BAD_DOMAINS = {"hrr.mlit.go.jp"}


def gn(q, lang):
    """Google News RSS search URL for a query in a given locale."""
    m = {"en-au": ("en-AU", "AU", "AU:en"),
         "en-in": ("en-IN", "IN", "IN:en"),
         "hi":    ("hi-IN", "IN", "IN:hi"),
         "mr":    ("mr-IN", "IN", "IN:mr")}
    hl, gl, ceid = m.get(lang, m["en-au"])
    return "https://news.google.com/rss/search?q=%s&hl=%s&gl=%s&ceid=%s" % (
        urllib.parse.quote(q), hl, gl, ceid)


# ---- Pulse (personal news) --------------------------------------------
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
LANG_KEYS = {"india", "movies"}

# "what's happening now" hooks for Spark topics
SPARK_WORLD = {
    "w_maths": ["mathematics competition", "maths puzzle"],
    "w_science": ["science discovery", "new invention"],
    "w_space": ["NASA space mission", "astronomy discovery"],
    "w_tennis": ["tennis ATP WTA"],
    "w_basketball": ["basketball NBA NBL"],
    "w_india": ["India history archaeology discovery", "Vedic mathematics"],
    "w_aussie": ["Australia wildlife nature"],
    "w_sport_au": ["AFL Australian football"],
}

# Spark news: photo-rich publisher feeds, grouped for natural mixing
SPARK_NEWS = {
    "bharat": ["https://timesofindia.indiatimes.com/rssfeeds/-2128936835.cms",
               "https://www.thehindu.com/news/national/feeder/default.rss",
               "https://www.thehindu.com/sport/feeder/default.rss",
               "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml",
               "https://feeds.feedburner.com/ndtvnews-top-stories"],
    "australia": ["https://www.abc.net.au/news/feed/51120/rss.xml",
                  "https://www.theguardian.com/au/rss",
                  "https://www.abc.net.au/news/feed/45910/rss.xml"],
    "science": ["https://feeds.bbci.co.uk/newsround/rss.xml",
                "https://www.snexplores.org/feed",
                "https://www.space.com/feeds/all",
                "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
                "https://www.sciencealert.com/feed",
                "https://phys.org/rss-feed/"],
    "sports": ["https://www.espncricinfo.com/rss/content/story/feeds/0.xml",
               "https://www.cricket.com.au/news/rss",
               "https://www.abc.net.au/news/feed/45910/rss.xml",
               "https://feeds.bbci.co.uk/sport/rss.xml"],
    "screen": ["https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml",
               "https://variety.com/v/film/feed/"],
    "tech": ["https://feeds.ign.com/ign/all",
             "https://www.cnet.com/rss/news/",
             "https://feeds.bbci.co.uk/news/technology/rss.xml"],
}


# ---- fetch + parse -----------------------------------------------------
def fetch(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/rss+xml, application/xml, text/xml, */*"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def clean(s):
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s).strip()


def norm_img(u):
    if not u:
        return ""
    u = u.strip()
    if u.startswith("//"):
        u = "https:" + u
    if not u.startswith("http"):
        return ""
    return u


def parse(raw):
    d = feedparser.parse(raw)
    out = []
    for e in d.entries:
        title = clean(e.get("title", ""))
        link = e.get("link", "") or ""
        src = surl = ""
        s = e.get("source")
        if isinstance(s, dict):
            src = clean(s.get("title", ""))
            surl = s.get("href", "") or ""
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
                if en.get("href"):
                    img = en["href"]
                    break
        if not img:
            for f in ("summary", "description"):
                m = re.search(r'<img[^>]+src=["\']([^"\']+)', e.get(f, "") or "")
                if m:
                    img = m.group(1)
                    break
        img = norm_img(img)
        if title and link:
            out.append({"title": title, "link": link, "source": src, "surl": surl,
                        "image": img, "date": ts})
    return out


def gather(urls, kid=False, cap=None):
    items, seen = [], set()
    for u in urls:
        try:
            got = parse(fetch(u))
        except Exception as ex:
            print("  ! fail", u, "->", type(ex).__name__, ex)
            continue
        print("  ok", len(got), u)
        for it in got:
            if SPAM.search(it["title"]):
                continue
            if kid and KID_BLOCK.search(it["title"]):
                continue
            dom = urllib.parse.urlparse(it.get("surl") or "").netloc.lower()
            if dom in BAD_DOMAINS:
                continue
            k = it["title"].lower()
            if k in seen:
                continue
            seen.add(k)
            items.append(it)
    items.sort(key=lambda x: x["date"], reverse=True)
    if cap:
        out, per = [], {}
        for it in items:
            s = it["source"] or ""
            if per.get(s, 0) >= cap:
                continue
            per[s] = per.get(s, 0) + 1
            out.append(it)
        items = out
    return items[:PER_KEY]


def main():
    gen = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ---- Pulse
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
    with open("feed.json", "w", encoding="utf-8") as f:
        json.dump({"generated": gen, "data": data}, f, ensure_ascii=False, separators=(",", ":"))
    print("WROTE feed.json:", sum(len(v) for v in data.values()), "items across", len(data), "keys")

    # ---- Spark "in the world"
    world = {}
    for key, qs in SPARK_WORLD.items():
        print("WORLD", key)
        world[key] = gather([gn(q, "en-au") for q in qs])[:20]
    os.makedirs("spark", exist_ok=True)
    with open(os.path.join("spark", "world.json"), "w", encoding="utf-8") as f:
        json.dump({"generated": gen, "world": world}, f, ensure_ascii=False, separators=(",", ":"))
    print("WROTE spark/world.json:", sum(len(v) for v in world.values()), "items across", len(world), "keys")

    # ---- Spark kids news (with real images)
    news = {}
    for key, urls in SPARK_NEWS.items():
        print("SPARK", key)
        news[key] = gather(urls, kid=True, cap=8)[:30]
    withimg = sum(1 for v in news.values() for it in v if it["image"])
    total = sum(len(v) for v in news.values())
    with open(os.path.join("spark", "feed.json"), "w", encoding="utf-8") as f:
        json.dump({"generated": gen, "data": news}, f, ensure_ascii=False, separators=(",", ":"))
    print("WROTE spark/feed.json:", total, "items across", len(news),
          "keys |", withimg, "with images")


if __name__ == "__main__":
    main()
