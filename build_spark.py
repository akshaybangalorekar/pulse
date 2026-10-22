#!/usr/bin/env python3
"""Spark edition builder.

Picks a small, finite set of stories for an 11-year-old Bharatiya boy in Melbourne,
pulls the actual article text, simplifies it for his reading age, and writes
spark/edition.json. Excludes topics the family does not want (religion news,
visa/immigration, geopolitics). Designed to be constructive and India-rooted.
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

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
TIMEOUT = 20
EDITION_SIZE = 6
BIRTHDAY = (2015, 6, 9)          # turns 12 on 9 June 2027

# --- what we never show -------------------------------------------------
KID_BLOCK = re.compile(
    r"\b(kill(?:ed|ing|s)?|dead|death|dies|died|murder(?:ed|s)?|stab(?:bed|bing)?|"
    r"gunman|shoot(?:ing|ings)?|rape|suicide|overdose|arrest(?:ed|s)?|jail(?:ed)?|"
    r"prison|war|missile|airstrike|bomb(?:ing|ed|s)?|blast|massacre|hostage|"
    r"terror(?:ist|ists|ism)?|houthi|nude|porn)\b", re.I)
NO_THANKS = re.compile(
    r"\b(pope|vatican|catholic|church|bishop|cardinal|archbishop|christian|jesus|"
    r"bible|gospel|priest|nun|missionary|visa|immigration|immigrant|migrant|asylum|"
    r"deport(?:ed|ation)?|green\s*card|geopolitic\w*|nato|sanction\w*|"
    r"security\s+council|diplomat\w*|treaty)\b", re.I)
SPAM = re.compile(r"(live\s*stream|streaming|watch\s+(live|online|free)|\u3010|\u3011|live\s*now)", re.I)
# what makes a story worth an 11-year-old's time, and what bores him
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

# --- sources (photo-rich publisher feeds) -------------------------------
FEEDS = {
    # written for children / genuinely engaging, not general adult news
    "kids": ["https://feeds.bbci.co.uk/newsround/rss.xml"],
    "science": ["https://www.snexplores.org/feed",
                "https://www.space.com/feeds/all",
                "https://www.sciencealert.com/feed"],
    "sport": ["https://www.cricket.com.au/news/rss",
              "https://www.espncricinfo.com/rss/content/story/feeds/0.xml"],
}
# keyword feeds (no images, but cover the India-specific asks)
KEYWORDS = {
    "bharat_tech": [("India semiconductor mission", "en-in"), ("India AI mission", "en-in"),
                    ("ISRO mission", "en-in"), ("India startup innovation", "en-in")],
    "vedic": [("Vedic science mathematics", "en-in"), ("Sanskrit heritage", "en-in"),
              ("Indian temple heritage restoration", "en-in"), ("Ayurveda research", "en-in")],
    "gaming": [("Nintendo", "en-au"), ("Roblox", "en-au"), ("Minecraft", "en-au")],
    "good": [("good news India", "en-in"), ("positive news science", "en-au")],
}

# --- thought-provoking question per category (rotates) ------------------
THINK = {
    "kids": ["What would you tell a friend about this?",
             "What surprised you most, and why?",
             "If you could change one thing about this, what would it be?"],
    "bharat": ["If you could fix one thing in your city, what would it be?",
               "Which Indian invention are you proudest of, and why?",
               "What would Chanakya say about this — what is the clever move here?"],
    "bharat_tech": ["India is building its own chips. Why does making things at home matter?",
                    "What would you build if you had a lab and no limits?",
                    "Which is harder — inventing something or making it for millions?"],
    "vedic": ["What did our ancestors know that we are only now rediscovering?",
              "How would you explain this idea to a friend in one line?",
              "What can we learn from how they solved problems with what they had?"],
    "science": ["What would you test if you had a real lab for a day?",
                "Which discovery would change the most lives in India?",
                "What question would you ask the scientist who did this?"],
    "sport": ["What does it take to stay calm in a big moment?",
              "Which matters more in sport — talent or practice?",
              "What would you tell a teammate who is about to give up?"],
    "gaming": ["What makes a game fun — the challenge or the story?",
               "If you designed a game about India, what would it be about?",
               "How could a game teach something useful without feeling like homework?"],
    "screen": ["What story would you make if you were a director?",
               "Which character would you want to be, and why?"],
    "world": ["What would you do to make this better if you were in charge?",
              "What can India learn from this, and what can it teach?"],
    "good": ["What small good thing could you do this week?",
             "Who in your life deserves a thank you?"],
}


def gn(q, lang):
    m = {"en-au": ("en-AU", "AU", "AU:en"), "en-in": ("en-IN", "IN", "IN:en")}
    hl, gl, ceid = m.get(lang, m["en-au"])
    return "https://news.google.com/rss/search?q=%s&hl=%s&gl=%s&ceid=%s" % (
        urllib.parse.quote(q), hl, gl, ceid)


def fetch_bytes(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
        "Accept": "application/rss+xml, application/xml, text/html, */*"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def clean(s):
    if not s:
        return ""
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = htmlmod.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


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
        if not img:
            m = re.search(r'<img[^>]+src=["\']([^"\']+)', e.get("summary", "") or e.get("description", "") or "")
            if m:
                img = m.group(1)
        if title and link:
            out.append({"title": title, "link": link, "source": src, "surl": surl,
                        "image": norm_img(img), "date": ts, "desc": desc})
    return out


def gather(feeds, kw, kid=True):
    items, seen = [], set()
    urls = list(feeds) + [gn(q, l) for q, l in kw]
    for u in urls:
        try:
            got = parse(fetch_bytes(u))
        except Exception as ex:
            print("  ! fail", u, type(ex).__name__)
            continue
        for it in got:
            t = it["title"]
            if SPAM.search(t) or (kid and (KID_BLOCK.search(t) or NO_THANKS.search(t))):
                continue
            k = t.lower()
            if k in seen:
                continue
            seen.add(k)
            items.append(it)
    items.sort(key=lambda x: x["date"], reverse=True)
    return items


# --- article text -------------------------------------------------------
def article_paragraphs(url):
    try:
        raw = fetch_bytes(url)
    except Exception:
        return []
    try:
        txt = raw.decode("utf-8", "ignore")
    except Exception:
        return []
    txt = re.sub(r"(?is)<(script|style|noscript|nav|footer|aside)[^>]*>.*?</\1>", " ", txt)
    m = re.search(r"(?is)<article[^>]*>(.*?)</article>", txt)
    body = m.group(1) if m else txt
    paras = re.findall(r"(?is)<p[^>]*>(.*?)</p>", body)
    out = []
    for p in paras:
        c = clean(p)
        if len(c) > 70:
            out.append(c)
    return out


BAD_OPEN = ("read more", "subscribe", "follow us", "click here", "sign up", "watch:",
            "advertisement", "get our", "download the", "share this", "you can also",
            "account subscription", "premium stories", "sign in", "image source",
            "image caption", "copy link", "click for next", "editorials", "opinions")


def simplify(paras, max_words):
    sents = []
    for p in paras:
        for s in re.split(r"(?<=[.!?])\s+", p):
            s = s.strip()
            w = len(s.split())
            low = s.lower()
            if 7 <= w <= 40 and not low.startswith(BAD_OPEN) and not any(b in low for b in
                    ("subscription", "premium stories", "sign in", "image source", "image caption")):
                sents.append(s)
    out, total = [], 0
    for s in sents[:7]:
        out.append(s)
        total += len(s.split())
        if total >= max_words:
            break
    if not out:
        return []
    # group into 2 short paragraphs
    half = max(1, len(out) // 2)
    return [" ".join(out[:half]), " ".join(out[half:])] if len(out) > 2 else [" ".join(out)]


def age_now():
    t = datetime.now(timezone.utc)
    y, m, d = BIRTHDAY
    return t.year - y - ((t.month, t.day) < (m, d))


def word_budget(age):
    return 90 if age <= 11 else 115 if age == 12 else 140


def score(it):
    t = it["title"]
    s = 0
    if ENGAGE.search(t):
        s += 2
    if DULL.search(t):
        s -= 2
    if CORP.search(t):
        s -= 6
    return s


def india_only(it):
    return bool(re.search(r"\b(india|indian|bharat|isro|drdo|semiconductor|chip|chipmaker)\b",
                          it["title"], re.I))


def main():
    age = age_now()
    budget = word_budget(age)
    gen = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("age", age, "word budget", budget)

    picked, think_i, seen_keys = [], 0, set()
    # groups whose publishers we can actually fetch and retell; the Vedic/Bharat-tech/
    # gaming reads come from the hand-written library in the app instead
    order = ["kids", "science", "sport"]
    per_group = 3
    for g in order:
        items = gather(FEEDS.get(g, []), KEYWORDS.get(g, []))
        if g == "bharat_tech":
            items = [it for it in items if india_only(it)]
        items = sorted(items, key=score, reverse=True)
        print("GROUP", g, len(items))
        taken = 0
        for it in items[:9]:
            if taken >= per_group:
                break
            if score(it) < -2:
                continue
            key = " ".join(it["title"].lower().split()[:4])
            if key in seen_keys:
                continue
            paras = article_paragraphs(it["link"]) if it["link"].startswith("http") else []
            if not paras:
                paras = [it.get("desc", "")] if it.get("desc") else []
            short = simplify(paras, budget)
            if sum(len(p.split()) for p in short) < MIN_WORDS:
                continue
            seen_keys.add(key)
            think = THINK.get(g, THINK["world"])
            picked.append({
                "kind": "news", "cat": g, "title": it["title"][:110],
                "paras": short, "image": it["image"], "source": it["source"],
                "date": it["date"], "think": think[think_i % len(think)],
            })
            think_i += 1
            taken += 1

    edition = picked[:EDITION_SIZE]
    os.makedirs("spark", exist_ok=True)
    with open(os.path.join("spark", "edition.json"), "w", encoding="utf-8") as f:
        json.dump({"generated": gen, "age": age, "items": edition}, f,
                  ensure_ascii=False, separators=(",", ":"))
    print("WROTE spark/edition.json:", len(edition), "stories |",
          sum(1 for x in edition if x["image"]), "with images")


if __name__ == "__main__":
    main()
