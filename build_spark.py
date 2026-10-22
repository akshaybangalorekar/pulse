#!/usr/bin/env python3
"""Spark edition builder.

Writes spark/edition.json with two halves:
  news  - a small, finite set of stories for an 11-year-old, retold in simple words
          from kid-facing sources (Press Gang News, TIME for Kids, Newsround,
          Science News Explores, Space.com)
  sport - tennis + basketball top updates, and junior (10-12) achievements
Excludes religion news, visa/immigration and geopolitics.
"""
import calendar
import html as htmlmod
import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import feedparser

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")
TIMEOUT = 20
BIRTHDAY = (2015, 6, 9)          # turns 12 on 9 June 2027

KID_BLOCK = re.compile(
    r"\b(kill(?:ed|ing|s)?|dead|death|dies|died|murder(?:ed|s)?|stab(?:bed|bing)?|"
    r"gunman|shoot(?:ing|ings)?|rape|suicide|overdose|arrest(?:ed|s)?|jail(?:ed)?|"
    r"prison|war|missile|airstrike|bomb(?:ing|ed|s)?|blast|massacre|hostage|"
    r"terror(?:ist|ists|ism)?|houthi|nude|porn)\b", re.I)
NO_THANKS = re.compile(
    r"\b(pope|vatican|catholic|church|bishop|cardinal|archbishop|christian|jesus|"
    r"bible|gospel|priest|nun|missionary|jewish|synagogue|mosque|islam\w*|muslim\w*|"
    r"ramadan|eid|christmas|easter|visa|immigration|immigrant|migrant|asylum|"
    r"deport(?:ed|ation)?|green\s*card|geopolitic\w*|nato|sanction\w*|"
    r"security\s+council|diplomat\w*|treaty)\b", re.I)
SPAM = re.compile(r"(live\s*stream|streaming|watch\s+(live|online|free)|\u3010|\u3011|live\s*now)", re.I)
ENGAGE = re.compile(
    r"\b(discover\w*|record|first|new|amazing|world|space|rocket|robot\w*|game|games|"
    r"launch\w*|invent\w*|rescue\w*|build\w*|young|student\w*|science|animal\w*|ocean|"
    r"dinosaur\w*|telescope|satellite|mission|trick|puzzle|mystery|ancient|heritage|"
    r"temple|chip\w*|semiconductor|nintendo|roblox|minecraft|pokemon|marvel|animation)\b", re.I)
DULL = re.compile(
    r"\b(court|supreme|scheme|regulator\w*|norms?|licence|license|policy|gst|tax|budget|"
    r"parliament|bill|committee|revenue|earnings|stock|shares|ipo|merger|inflation|"
    r"quarterly|profit|stake|tender|tariff|compliance|protocol|bureau|standards?)\b", re.I)
CORP = re.compile(r"\b(sue[sd]?|lawsuit|shareholder\w*|investor\w*|ceo|board|acquisition|deal)\b", re.I)
MIN_WORDS = 32

# kid-facing news sources the family asked for (those that publish usable feeds)
FEEDS = {
    "pressgang": ["https://pressgang.news/feed/"],
    "timeforkids": ["https://www.timeforkids.com/feed/"],
    "newsround": ["https://feeds.bbci.co.uk/newsround/rss.xml"],
    "science": ["https://www.snexplores.org/feed", "https://www.space.com/feeds/all"],
}
GROUP_NAME = {"pressgang": "Press Gang News", "timeforkids": "TIME for Kids",
              "newsround": "Behind the News", "science": "Science & space"}

# sport: headline updates + junior achievements
SPORT_QUERIES = {
    "Tennis": [("tennis ATP WTA", "en-au"), ("Grand Slam tennis", "en-au")],
    "Basketball": [("basketball NBA", "en-au"), ("NBL basketball", "en-au")],
    "Junior stars (10-12)": [
        ("junior tennis ranking Australia", "en-au"),
        ("Australian junior tennis champion", "en-au"),
        ("under 12 basketball Australia", "en-au"),
        ("India junior tennis champion", "en-in"),
    ],
}

BAD_OPEN = ("read more", "subscribe", "follow us", "click here", "sign up", "watch:",
            "advertisement", "get our", "download the", "share this", "you can also",
            "account subscription", "premium stories", "sign in", "image source",
            "image caption", "copy link", "click for next", "editorials", "opinions")


def gn(q, lang):
    m = {"en-au": ("en-AU", "AU", "AU:en"), "en-in": ("en-IN", "IN", "IN:en")}
    hl, gl, ceid = m.get(lang, m["en-au"])
    return ("https://news.google.com/rss/search?q=" + urllib.parse.quote(q)
            + "&hl=" + hl + "&gl=" + gl + "&ceid=" + ceid)


def fetch_bytes(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/html, */*"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def clean(s):
    if not s:
        return ""
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", htmlmod.unescape(s)).strip()


def norm_img(u):
    if not u:
        return ""
    u = u.strip()
    if u.startswith("//"):
        u = "https:" + u
    return u if u.startswith("http") else ""


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
                pass
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
        desc = ""
        for f in ("summary", "description"):
            if e.get(f):
                desc = clean(e.get(f))
                break
        if title and link:
            out.append({"title": title, "link": link, "source": src, "surl": surl,
                        "image": norm_img(img), "date": ts, "desc": desc})
    return out


def ok(it):
    t = it["title"]
    return not (SPAM.search(t) or KID_BLOCK.search(t) or NO_THANKS.search(t))


def score(it):
    t = it["title"]
    s = 2 if ENGAGE.search(t) else 0
    s -= 2 if DULL.search(t) else 0
    s -= 6 if CORP.search(t) else 0
    return s


def gather(urls):
    items, seen = [], set()
    for u in urls:
        try:
            got = parse(fetch_bytes(u))
        except Exception as ex:
            print("  ! fail", u, type(ex).__name__)
            continue
        print("  ok", len(got), u)
        for it in got:
            if not ok(it):
                continue
            k = it["title"].lower()
            if k in seen:
                continue
            seen.add(k)
            items.append(it)
    items.sort(key=lambda x: x["date"], reverse=True)
    return items


def article_paragraphs(url):
    try:
        txt = fetch_bytes(url).decode("utf-8", "ignore")
    except Exception:
        return []
    txt = re.sub(r"(?is)<(script|style|noscript|nav|footer|aside)[^>]*>.*?</\1>", " ", txt)
    m = re.search(r"(?is)<article[^>]*>(.*?)</article>", txt)
    body = m.group(1) if m else txt
    out = []
    for p in re.findall(r"(?is)<p[^>]*>(.*?)</p>", body):
        c = clean(p)
        if len(c) > 70:
            out.append(c)
    return out


def simplify(paras, max_words):
    sents = []
    for p in paras:
        for s in re.split(r"(?<=[.!?])\s+", p):
            s = s.strip()
            w = len(s.split())
            low = s.lower()
            if (7 <= w <= 40 and not low.startswith(BAD_OPEN)
                    and not any(b in low for b in ("subscription", "premium stories",
                                                   "sign in", "image source", "image caption"))):
                sents.append(s)
    out, total = [], 0
    for s in sents[:7]:
        out.append(s)
        total += len(s.split())
        if total >= max_words:
            break
    if not out:
        return []
    half = max(1, len(out) // 2)
    return [" ".join(out[:half]), " ".join(out[half:])] if len(out) > 2 else [" ".join(out)]


def age_now():
    t = datetime.now(timezone.utc)
    y, m, d = BIRTHDAY
    return t.year - y - ((t.month, t.day) < (m, d))


def word_budget(age):
    return 90 if age <= 11 else 115 if age == 12 else 140


THINK = {
    "pressgang": ["What would you tell a friend about this?",
                  "What surprised you most, and why?"],
    "timeforkids": ["If you could change one thing about this, what would it be?",
                    "How would you explain this to someone younger?"],
    "newsround": ["What would you do if you were in charge?",
                  "What is the clever move here, do you think?"],
    "science": ["What would you test if you had a real lab for a day?",
                "Which discovery would help the most people?"],
}


def build_news(age, budget):
    news, seen, taken = [], set(), {}
    for g, feeds in FEEDS.items():
        items = gather(feeds)
        items.sort(key=score, reverse=True)
        print("GROUP", g, len(items))
        n = 0
        for it in items[:8]:
            if n >= 2:
                break
            key = " ".join(it["title"].lower().split()[:4])
            if key in seen:
                continue
            paras = article_paragraphs(it["link"]) if it["link"].startswith("http") else []
            if not paras:
                paras = [it["desc"]] if it["desc"] else []
            short = simplify(paras, budget)
            if sum(len(p.split()) for p in short) < MIN_WORDS:
                continue
            seen.add(key)
            th = THINK.get(g, THINK["science"])
            news.append({"kind": "news", "cat": g, "show": GROUP_NAME.get(g, g),
                         "title": it["title"][:110], "paras": short,
                         "image": it["image"], "source": it["source"], "date": it["date"],
                         "think": th[taken.get(g, 0) % len(th)]})
            taken[g] = taken.get(g, 0) + 1
            n += 1
    return news


def build_sport():
    sport = []
    for section, queries in SPORT_QUERIES.items():
        items, seen = [], set()
        for q, lang in queries:
            try:
                got = parse(fetch_bytes(gn(q, lang)))
            except Exception as ex:
                print("  ! sport fail", q, type(ex).__name__)
                continue
            for it in got:
                if not ok(it):
                    continue
                k = it["title"].lower()
                if k in seen:
                    continue
                seen.add(k)
                items.append(it)
        items.sort(key=lambda x: x["date"], reverse=True)
        for it in items[:6]:
            sport.append({"kind": "head", "section": section, "title": it["title"][:110],
                          "source": it["source"], "date": it["date"]})
        print("SPORT", section, len(items))
    return sport


def main():
    age = age_now()
    gen = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("age", age)
    news = build_news(age, word_budget(age))
    sport = build_sport()
    os.makedirs("spark", exist_ok=True)
    with open(os.path.join("spark", "edition.json"), "w", encoding="utf-8") as f:
        json.dump({"generated": gen, "age": age, "news": news, "sport": sport}, f,
                  ensure_ascii=False, separators=(",", ":"))
    print("WROTE spark/edition.json:", len(news), "news |", len(sport), "sport headlines")


if __name__ == "__main__":
    main()
