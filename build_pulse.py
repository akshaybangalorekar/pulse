#!/usr/bin/env python3
"""Pulse builder.

Writes pulse.json: a set of sections. Economy/geopolitics, Bharat & Australia, tennis
and football stories are FETCHED and CONDENSED into our own short summary (not the raw
page). Listing sections (Marathi events, comedy, monster trucks, music, Indian sport)
are headline feeds. Parenting is hand-written.
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

KID_BLOCK = re.compile(
    r"\b(kill(?:ed|ing|s)?|dead|death|dies|died|murder(?:ed|s)?|stab(?:bed|bing)?|"
    r"gunman|shoot(?:ing|ings)?|rape|suicide|overdose|nude|porn)\b", re.I)
SPAM = re.compile(r"(live\s*stream|streaming|watch\s+(live|online|free)|\u3010|\u3011|live\s*now|"
                  r"horoscope|astrolog\w*|zodiac|cricket\s+score|dream11|betting\s+tips)", re.I)
OPINION = re.compile(r"^(opinion|editorial|comment|analysis:)\b", re.I)
# the brief is economics and geopolitics, so keep inflammatory communal framing out
INFLAME = re.compile(
    r"\b(communal\w*|riots?|jihad\w*|love\s+jihad|anti-?national|urban\s+naxal\w*|"
    r"tukde|traitor\w*|appeasement|vote\s+bank|infiltrat\w*|lynch\w*|conversion)\b", re.I)
ENGAGE = re.compile(
    r"\b(econom\w*|market\w*|trade|tariff\w*|inflation|interest\s+rate|growth|gdp|export\w*|"
    r"import\w*|rupee|dollar|investment|manufactur\w*|semiconductor\w*|energy|oil|supply\s+chain|"
    r"geopolitic\w*|sanction\w*|treaty|summit|alliance|border|diplomat\w*|central\s+bank|rbi|"
    r"reserve\s+bank|budget|deal|merger|acquisition|startup\w*|jobs?|unemploy\w*|wage\w*|"
    r"tax\w*|policy|reform\w*|infrastructure|port|shipping|bank\w*|currency|commodit\w*)\b", re.I)
DULL = re.compile(r"\b(horoscope|astrology|zodiac|celebrity|gossip|royal\w*|"
                  r"crossword|quiz\s+answers)\b", re.I)
US_TAG = re.compile(r"\b(india|indian|bharat|australia|australian|melbourne|sydney|rupee|"
                    r"sensex|nifty|asx|rbi|reserve\s+bank\s+of\s+australia)\b", re.I)

BOILER = re.compile(
    r"(stock tips|share market|budget 20\d\d|track latest|market news\s*,|whatsapp|telegram|"
    r"download (the|our) app|follow us|subscribe|also read|read more|click here|trending|"
    r"top gainers|top losers|sensex and nifty|disclaimer|investment advice|views expressed|"
    r"photo credit|getty images|ai quick read|quick read|advertisement|sponsored|"
    r"copyright|all rights reserved|terms of use|privacy policy|toi\.in|be the first to comment|"
    r"catch all the|live updates|stay tuned|for more|first published|account subscription|"
    r"premium stories|the view from india|kyb and kyc|business behind the wealth creator|"
    r"editorials\s*,\s*opinions|first day first show|looking at world affairs|"
    r"get unlimited access|to continue reading|already a subscriber|log ?in|register now|"
    r"bond yield and cds|business of odd things|will they decide the fate|"
    r"text settings|story text|size small|standard wide|links standard|subscribers only|"
    r"credit:|getty images|afp/|aurich lawson|photo:|image:|"
    r"inside an industry th|top gainers and losers|mutual fund|ipo watch|"
    r"this article is|available exclusively|part \d+$|click for next|today'?s cache|"
    r"your download of|weekly newsletter|will become available on the|share a a a|"
    r"most weeks open with|science for all|the top \d+ technology stories|health matters|"
    r"writes to you on|books of the week|the hindu on books|e-?paper|today'?s paper|"
    r"newsletter from|subscribe to our|sign up for our|our newsletter)", re.I)
CREDIT = re.compile(r"^\s*[\(\[]\s*(photo|image|credit|source|file|reuters|ap|pti|afp|bloomberg|getty)[^)\]]*[\)\]]\s*", re.I)

MIN_WORDS = 40
BAD_OPEN = ("read more", "subscribe", "follow us", "click here", "sign up", "watch:",
            "advertisement", "get our", "download the", "also read", "read |", "image source",
            "image caption", "sign in", "premium", "toi", "copy link", "trending")

TENNIS_FEEDS = ["https://www.tennismajors.com/feed/",
                "https://www.ubitennis.net/feed/",
                "https://tennishead.net/feed/",
                "https://lastwordonsports.com/tennis/feed/"]

SECTIONS = [
    {"id": "economy", "name": "Economy & geopolitics", "emoji": "\U0001F30F", "kind": "story",
     "want": 4, "prefer_tag": True, "rewrite": True,
     "feeds": ["https://economictimes.indiatimes.com/news/economy/rssfeeds/1373380680.cms",
               "https://economictimes.indiatimes.com/industry/rssfeeds/13352306.cms",
               "https://www.livemint.com/rss/economy",
               "https://theprint.in/category/economy/feed/",
               "https://organiser.org/feed/",
               "https://feeds.bbci.co.uk/news/business/rss.xml",
               "https://feeds.bbci.co.uk/news/world/rss.xml",
               "https://www.smh.com.au/rss/business.xml",
               "https://www.spectator.com.au/feed/"]},

    {"id": "bharat_au", "name": "Bharat & Australia", "emoji": "\U0001F1E6\U0001F1FA", "kind": "story",
     "want": 2, "must_tag": True, "rewrite": True,
     "feeds": ["https://www.smh.com.au/rss/business.xml",
               "https://www.spectator.com.au/feed/",
               "https://www.macrobusiness.com.au/feed/",
               "https://economictimes.indiatimes.com/news/economy/rssfeeds/1373380680.cms",
               "https://www.livemint.com/rss/economy",
               "https://theprint.in/category/economy/feed/"]},

    {"id": "finance", "name": "Finance & markets", "emoji": "\U0001F4C8", "kind": "story",
     "want": 2, "rewrite": True,
     "feeds": ["https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
               "https://www.livemint.com/rss/markets",
               "https://www.smh.com.au/rss/business.xml"]},

    {"id": "tech", "name": "Technology & AI", "emoji": "\U0001F916", "kind": "story",
     "want": 3, "rewrite": True,
     "feeds": ["https://feeds.arstechnica.com/arstechnica/index",
               "https://spectrum.ieee.org/feeds/feed.rss",
               "https://www.newscientist.com/feed/home/",
               "https://www.technologyreview.com/feed/"]},

    {"id": "tennis", "name": "Tennis", "emoji": "\U0001F3BE", "kind": "story",
     "want": 4, "feeds": TENNIS_FEEDS},

    {"id": "football", "name": "Football", "emoji": "\u26BD", "kind": "head", "want": 6,
     "feeds": ["https://feeds.bbci.co.uk/sport/football/rss.xml"],
     "queries": [("Premier League", "en-au"), ("A-League", "en-au"),
                 ("Indian Super League", "en-in")]},

    {"id": "indiasport", "name": "Indian sports", "emoji": "\U0001F3CF", "kind": "head", "want": 6,
     "feeds": [],
     "queries": [("India cricket team", "en-in"), ("Indian hockey team", "en-in"),
                 ("Indian badminton", "en-in"), ("India athletics", "en-in")]},

    {"id": "marathi", "name": "Melbourne Marathi", "emoji": "\U0001F3AD", "kind": "head", "want": 6,
     "feeds": [],
     "queries": [("Marathi Melbourne", "en-au"), ("Maharashtra Mandal Melbourne", "en-au"),
                 ("Marathi cultural event Melbourne", "en-au"), ("Marathi natak Melbourne", "en-au")]},

    {"id": "comedy", "name": "Indian stand-up", "emoji": "\U0001F602", "kind": "head", "want": 6,
     "feeds": [],
     "queries": [("Indian stand-up comedy", "en-in"), ("stand-up comedy India tour", "en-in"),
                 ("Indian comedy show Australia", "en-au")]},

    {"id": "monster", "name": "Monster racing", "emoji": "\U0001F69A", "kind": "head", "want": 6,
     "feeds": [],
     "queries": [("Monster Jam", "en-au"), ("monster truck Australia", "en-au"),
                 ("monster truck show", "en-au")]},

    {"id": "music", "name": "Music shows", "emoji": "\U0001F3B5", "kind": "head", "want": 6,
     "feeds": [],
     "queries": [("concert Melbourne", "en-au"), ("music tour Australia", "en-au"),
                 ("music festival Melbourne", "en-au"), ("Indian concert Australia", "en-au")]},
]

PARENTING = [
    {"t": "Friendships are built by repeated contact, not by being liked",
     "hook": "This is the single most useful fact in the whole guide.",
     "paras": ["Studies of primary-school classrooms found that children seated next to each "
               "other were far more likely to become friends than children seated across the "
               "room. When teachers changed the seating, new friendships formed with the new "
               "neighbours.",
               "So the engine is: same place, same people, same activity, over and over. The day "
               "at the yo-yo bar followed by basketball is that engine working - shared activity "
               "changed how the other boy treated him. It was not luck."],
     "do": "Pick one activity he already likes and commit to it weekly for a full term."},

    {"t": "Keep the proximity - change the watching",
     "hook": "Your instinct is half right, and the other half matters.",
     "paras": ["You are right that being around the group matters: children nominate as friends "
               "the children they see and interact with most. 'Out of sight, out of mind' is real "
               "for acquaintances.",
               "But guidance written for schools is blunt: merely remaining beside a group is not "
               "friendship. A child who hovers is read as a bystander rather than a player, and it "
               "holds him in the one-down position. Watching has a use - but only as the first "
               "twenty seconds of joining in, never as the endpoint."],
     "do": "Keep telling him to stay near the group. Add: 'then take a job in the game'."},

    {"t": "Teach 'watch, then blend'",
     "hook": "The best way to join a game is not to ask.",
     "paras": ["Most of us were told to walk up and say 'Can I play?' But that makes everyone stop "
               "and look at him, and makes 'no' very easy.",
               "The better sequence, used by people who study play: watch for about twenty seconds "
               "to learn the game and where the line is, then slide into the action without "
               "stopping it. Take the end of the line. Stand in the outfield. Pick up the ball and "
               "pass it back."],
     "do": "Rehearse it at home in five minutes. Ask him to name the 'easiest job' in each game."},

    {"t": "Host one friend at a time - this is the biggest lever you control",
     "hook": "The child who invites is rarely short of friends.",
     "paras": ["Pick a child he has had fun with in the last month, not someone he admires from "
               "afar. Invite one person for one to two hours. Put away anything precious, have two "
               "activities ready, start with a snack, and let the guest choose sometimes.",
               "Keep it short and end while they are both still enjoying it. Then leave a few weeks "
               "before inviting the same child again, so the invitation can come back to him."],
     "do": "Text one parent this week and set a date for the school holidays."},

    {"t": "Ask the teacher one specific question",
     "hook": "Teachers see the playground. Ask them to name names.",
     "paras": ["Ask two things: who does he play well with, and could he be seated near them or "
               "paired with them for group work?",
               "Seating is one of the few levers that reliably creates new friendships, and it is "
               "invisible to the children - no one has to know it was arranged."],
     "do": "Email the teacher this week with those two questions."},

    {"t": "Do not push into a group that is rejecting him",
     "hook": "Here the advice is the opposite of persistence.",
     "paras": ["Where a group is actively excluding him, the guidance is to back off - when you "
               "back off from people, they can move towards you. Put his energy into two or three "
               "other children instead of one closed circle.",
               "Friends in more than one place - school, a club, family friends - also make him far "
               "less vulnerable when one group turns cold."],
     "do": "Help him list three children outside the difficult group he could get to know."},

    {"t": "One or two good friends is the goal - not popularity",
     "hook": "Child psychologists say this plainly.",
     "paras": ["Kids need one or two good friends. You do not need to worry about him being the "
               "most popular child in the class.",
               "His warmth and kindness are already the raw material. Treat this as coaching a "
               "skill, not fixing a fault - if he feels like a project, he will resist."],
     "do": "Say his strengths out loud, often. Confidence is what carries a child into a group."},

    {"t": "Playing and talking with girls is normal and good",
     "hook": "Children believe gender matters far more than it actually does.",
     "paras": ["In one large classroom experiment, simply seating boys and girls next to each "
               "other doubled how often they became friends.",
               "Girls' play tends to build conversation, turn-taking and inventing games together; "
               "boys' play builds bigger, faster group play. Being good at both widens his circle."],
     "do": "No action needed. Just do not let him think it is odd."},

    {"t": "When to get more help",
     "hook": "Ordinary friendship difficulty is not a disorder.",
     "paras": ["Get more support if he becomes reluctant to go to school, is persistently "
               "distressed, has changes in sleep or appetite, or says it is happening all the time "
               "and he cannot make it stop.",
               "Start with his teacher, then the school counsellor, then your GP for a referral. "
               "Kids Helpline is free and open 24/7 on 1800 55 1800, for children and for parents."],
     "do": "Save Kids Helpline in your phone: 1800 55 1800."},
]


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
        if not img:
            m = re.search(r'<img[^>]+src=["\']([^"\']+)', e.get("summary", "") or "")
            if m:
                img = m.group(1)
        desc = ""
        for f in ("summary", "description"):
            if e.get(f):
                desc = clean(e.get(f))
                break
        if title and link:
            out.append({"title": title, "link": link, "source": src,
                        "image": norm_img(img), "date": ts, "desc": desc})
    return out


def ok(it):
    t = it["title"]
    return not (SPAM.search(t) or KID_BLOCK.search(t) or DULL.search(t)
                or OPINION.search(t) or INFLAME.search(t))


def score(it):
    t = it["title"]
    return (2 if ENGAGE.search(t) else 0) - (2 if DULL.search(t) else 0)


def gather(feeds, queries=None, tag_only=False, prefer_tag=False):
    urls = list(feeds or []) + [gn(q, l) for q, l in (queries or [])]
    items, seen = [], set()
    for u in urls:
        try:
            got = parse(fetch_bytes(u))
        except Exception as ex:
            print("  ! fail", u[:60], type(ex).__name__)
            continue
        for it in got:
            if not ok(it):
                continue
            k = it["title"].lower()
            if k in seen:
                continue
            seen.add(k)
            items.append(it)
    if tag_only:
        items = [i for i in items if US_TAG.search(i["title"])]
    if prefer_tag:
        items.sort(key=lambda x: (1 if US_TAG.search(x["title"]) else 0, score(x), x["date"]),
                   reverse=True)
    else:
        items.sort(key=lambda x: (score(x), x["date"]), reverse=True)
    return items


def article_text(url):
    try:
        txt = fetch_bytes(url).decode("utf-8", "ignore")
    except Exception:
        return []
    txt = re.sub(r"(?is)<(script|style|noscript|nav|footer|aside|form)[^>]*>.*?</\1>", " ", txt)
    m = re.search(r"(?is)<article[^>]*>(.*?)</article>", txt)
    body = m.group(1) if m else txt
    out = []
    for p in re.findall(r"(?is)<p[^>]*>(.*?)</p>", body):
        c = clean(p)
        if len(c) > 70:
            out.append(c)
    return out


def sentences(paras):
    sents = []
    for p in paras:
        for s in re.split(r"(?<=[.!?])\s+", p):
            s = CREDIT.sub("", s).strip()
            w = len(s.split())
            low = s.lower()
            if w < 8 or w > 42:
                continue
            if low.startswith(BAD_OPEN) or BOILER.search(s):
                continue
            if s.count("(") != s.count(")") or s.count("[") != s.count("]"):
                continue
            if re.search(r"[\u00bb\u2022|]", s):
                continue
            if not re.match(r"^[A-Z0-9\"\u2018\u201c]", s):
                continue
            sents.append(s)
    return sents


def condense(paras, budget=130):
    out, total = [], 0
    for s in sentences(paras):
        out.append(s)
        total += len(s.split())
        if total >= budget:
            break
    if not out:
        return []
    if len(out) <= 3:
        return [" ".join(out)]
    third = max(1, len(out) // 3)
    return [" ".join(out[:third]), " ".join(out[third:2 * third]), " ".join(out[2 * third:])]


def impact_line(paras):
    """A sentence from the source that names India or Australia - never invented."""
    for s in sentences(paras):
        if US_TAG.search(s):
            return s if len(s.split()) <= 40 else " ".join(s.split()[:38]) + "."
    return ""


USED = set()
SEEN_FILE = "pulse-seen.json"
SEEN_DAYS = 60
SEEN = {}


def key_of(title):
    t = re.sub(r"[^a-z0-9 ]", " ", (title or "").lower())
    return " ".join(t.split()[:8])


def load_seen():
    global SEEN
    try:
        raw = json.load(open(SEEN_FILE, encoding="utf-8"))
        if isinstance(raw, dict):
            cut = time.time() - SEEN_DAYS * 86400
            SEEN = {k: v for k, v in raw.items() if isinstance(v, (int, float)) and v >= cut}
    except Exception:
        SEEN = {}
    print("SEEN memory:", len(SEEN), "stories in the last %d days" % SEEN_DAYS)


def mark_seen(title):
    SEEN[key_of(title)] = time.time()


def save_seen():
    cut = time.time() - SEEN_DAYS * 86400
    keep = {k: v for k, v in SEEN.items() if v >= cut}
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(keep, f, separators=(",", ":"))
    print("SEEN saved:", len(keep))


LLM_BASE = "https://text.pollinations.ai/"
LLM_SLEEP = 31
LLM_BUDGET = 12
_llm = {"n": 0}


def llm(prompt):
    if _llm["n"] >= LLM_BUDGET:
        return None
    _llm["n"] += 1
    try:
        req = urllib.request.Request(LLM_BASE + urllib.parse.quote(prompt),
                                     headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=75) as r:
            txt = r.read().decode("utf-8", "ignore").strip()
        low = txt.lower()
        if len(txt) > 80 and "free limit" not in low and "rate limit" not in low \
                and "payment required" not in low and not txt.startswith("{"):
            time.sleep(LLM_SLEEP)
            return txt
    except Exception as ex:
        print("  ! llm", type(ex).__name__)
    time.sleep(LLM_SLEEP)
    return None


def adult_prompt(title, text):
    return (
        "You are a sharp business, finance and technology editor. Your reader is an informed "
        "Indian professional living in Melbourne. He wants to be up to date and to understand "
        "the implications, not just the headline.\n\n"
        "Rewrite the story below so it is short, complete and genuinely useful.\n\n"
        "Rules:\n"
        "- 90 to 120 words, in two or three short paragraphs.\n"
        "- Paragraph 1: what happened, in plain English.\n"
        "- Paragraph 2: why it happened and what it means - the implication, not just the event.\n"
        "- Optional last line: what to watch next.\n"
        "- Explain every technical or financial term in the same sentence it appears, for example "
        "'composite PMI, a monthly survey of business activity'.\n"
        "- Spell out every abbreviation the first time (say 'the United States Federal Reserve', "
        "not 'the Fed').\n"
        "- Every sentence 22 words or fewer. No semicolons.\n"
        "- Use only facts from the story. Never invent numbers, names or quotes.\n"
        "- Neutral and factual. No hype, no editorialising, no emojis, no links.\n\n"
        "TITLE: %s\n\nSTORY: %s\n" % (title, text[:2600])
    )


def adult_clarity_ok(paras):
    text = " ".join(paras).strip()
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if not sents:
        return False, "empty"
    words = sum(len(s.split()) for s in sents)
    if words < 75:
        return False, "too short (%d words)" % words
    if words > 145:
        return False, "too long (%d words)" % words
    longest = max(len(s.split()) for s in sents)
    if longest > 24:
        return False, "sentence of %d words" % longest
    if any(";" in s for s in sents):
        return False, "semicolon"
    if not re.search(r"\b(because|which means|that means|in effect|as a result|so |"
                     r"this means|the implication|what it means)\b", text, re.I):
        return False, "no implication"
    return True, ""


def parse_llm(out):
    out = re.sub(r"```[a-z]*|```", "", out).strip()
    paras = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", out) if p.strip()]
    paras = [p for p in paras if len(p.split()) >= 8][:3]
    if not paras and out:
        paras = [out]
    return paras


def rewrite_story(title, paras):
    """Short, complete, jargon explained. Returns (paras, rewritten?)."""
    text = " ".join(paras)[:2600]
    if not text:
        return paras, False
    out = llm(adult_prompt(title, text))
    if not out:
        return paras, False
    lp = parse_llm(out)
    ok, why = adult_clarity_ok(lp)
    if ok:
        return lp, True
    print("  ~ clarity:", why)
    return paras, False


def build_story_section(sec):
    items = gather(sec.get("feeds"), sec.get("queries"), tag_only=sec.get("must_tag", False),
                   prefer_tag=sec.get("prefer_tag", False))
    print("SECTION", sec["id"], len(items))
    out, seen, n, stale = [], set(), 0, []
    for it in items[:16]:
        if n >= sec["want"]:
            break
        key = " ".join(it["title"].lower().split()[:4])
        if key in seen or it["title"].lower() in USED:
            continue
        if key_of(it["title"]) in SEEN:
            stale.append(it)
            continue
        paras = article_text(it["link"]) if it["link"].startswith("http") else []
        if not paras:
            paras = [it["desc"]] if it["desc"] else []
        if sec.get("must_tag") and not US_TAG.search(it["title"] + " " + " ".join(paras[:3])):
            continue
        short = condense(paras)
        if sec.get("rewrite"):
            short, _rw = rewrite_story(it["title"], paras)
        if sum(len(p.split()) for p in short) < MIN_WORDS:
            continue
        seen.add(key)
        USED.add(it["title"].lower())
        imp = impact_line(paras)
        if imp:
            body = " ".join(short).lower()
            if imp.lower().strip(" .")[:60] in body:
                imp = ""      # already in the text - do not repeat it
        out.append({"kind": "story", "title": it["title"][:120], "paras": short,
                    "impact": imp, "image": it["image"],
                    "source": it["source"], "link": it["link"], "date": it["date"]})
        n += 1
    if not out and stale:
        stale.sort(key=lambda x: SEEN.get(key_of(x["title"]), 0))
        it = stale[0]
        paras = article_text(it["link"]) if it["link"].startswith("http") else []
        if not paras:
            paras = [it["desc"]] if it["desc"] else []
        short = condense(paras)
        if sum(len(p.split()) for p in short) >= MIN_WORDS:
            out.append({"kind": "story", "title": it["title"][:120], "paras": short,
                        "impact": impact_line(paras), "image": it["image"],
                        "source": it["source"], "link": it["link"], "date": it["date"]})
    return out


def build_head_section(sec):
    items = gather(sec.get("feeds"), sec.get("queries"))
    print("SECTION", sec["id"], len(items))
    out, seen, stale = [], set(), []
    for it in items:
        if len(out) >= sec["want"]:
            break
        k = it["title"].lower()
        if k in seen or k in USED:
            continue
        if key_of(it["title"]) in SEEN:
            stale.append(it)
            continue
        seen.add(k)
        USED.add(k)
        mark_seen(it["title"])
        out.append({"kind": "head", "title": it["title"][:120], "source": it["source"],
                    "link": it["link"], "date": it["date"], "image": it["image"]})
    return out


def main():
    load_seen()
    gen = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sections = []
    for sec in SECTIONS:
        items = build_story_section(sec) if sec["kind"] == "story" else build_head_section(sec)
        if items:
            sections.append({"id": sec["id"], "name": sec["name"], "emoji": sec["emoji"],
                             "items": items})
    sections.append({"id": "parenting", "name": "Parenting", "emoji": "\U0001F468\u200D\U0001F469\u200D\U0001F466",
                     "items": [{"kind": "card", "title": p["t"], "hook": p["hook"],
                                "paras": p["paras"], "do": p["do"]} for p in PARENTING]})
    payload = {"generated": gen, "sections": sections}
    with open("pulse.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    save_seen()
    print("WROTE pulse.json:", sum(len(s["items"]) for s in sections), "items in",
          len(sections), "sections | llm calls:", _llm["n"])


if __name__ == "__main__":
    main()
