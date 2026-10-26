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
    r"security\s+council|diplomat\w*|treaty|weapon\w*|military|warhead|arms\s+race|"
    r"orbital\s+weapon)\b", re.I)
SPAM = re.compile(r"(live\s*stream|streaming|watch\s+(live|online|free)|\u3010|\u3011|live\s*now)", re.I)
# sport: no gossip, no personal life
GOSSIP = re.compile(
    r"\b(girlfriend|boyfriend|wife|husband|dating|wedding|divorce|engaged|engagement|"
    r"romance|affair|feud|spat|trolls?|hits back|war of words|personal life|off the field|"
    r"nightclub|vacation|holiday snaps|shirtless|bikini|swipes? at|dig at|takes aim|"
    r"lashes out|secret love|rumour mill|gossip|retirement|retires|breaks silence|"
    r"opens up about|confirms)\b", re.I)
# screen: keep films and shows age-appropriate
SCREEN_BLOCK = re.compile(
    r"\b(horror|gore|gruesome|slasher|explicit|erotic|18\+|r-rated|nc-17|adult film|"
    r"true crime|serial killer|drug cartel|gang war|nude|sex scene|disturbing|"
    r"nightmare|psychopath|crime thriller)\b", re.I)
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
FUNDRAISER = re.compile(
    r"\b(fundraiser|fund-?raising|colour fun run|fun run|mufti|cake stall|bake sale|"
    r"sausage sizzle|school fete|raffle|trivia night|book fair|school newsletter|our school|"
    r"parents and citizens|P&C|PTA|sports carnival|assembly|newsletter|disco|jumble sale)\b", re.I)
ANALYSIS = re.compile(
    r"\b(analysis|analys\w*|tactics?|tactical|how|why|explained|breakdown|strategy|preview|"
    r"review|deep dive|numbers|statistics|stats|form|blueprint|masterclass|lessons|"
    r"what we learned|patterns)\b", re.I)
FRONTIER = re.compile(
    r"\b(quantum|qubit\w*|artificial intelligence|\bai\b|neural|machine learning|robot\w*|"
    r"drone\w*|crispr|gene\w*|biotech\w*|bio-?robot\w*|synthetic biolog\w*|semiconductor\w*|"
    r"chip\w*|laser\w*|fusion|battery|batteries|satellite\w*|rocket\w*|brain-?computer|"
    r"3d[- ]print\w*|soft robot\w*|swarm\w*|autonomous|algorithm\w*|protein\w*|vaccine\w*|"
    r"telescope\w*|particle\w*|physics|mathematic\w*|superconduct\w*|nanotech\w*)\b", re.I)
MIN_WORDS = 45

# kid-facing news sources the family asked for (those that publish usable feeds)
FEEDS = {
    # STEM and inventions lead, so curiosity is caught first
    "frontier": ["https://spectrum.ieee.org/feeds/topic/robotics.rss",
                 "https://feeds.arstechnica.com/arstechnica/index",
                 "https://www.quantamagazine.org/feed/",
                 "https://www.newscientist.com/feed/home/"],
    "science": ["https://www.snexplores.org/feed", "https://www.space.com/feeds/all"],
    "pressgang": ["https://pressgang.news/feed/"],
    "timeforkids": ["https://www.timeforkids.com/feed/"],
    "newsround": ["https://feeds.bbci.co.uk/newsround/rss.xml"],
    "screen": [],
}
# keyword queries per group (turned into Google News feeds at run time)
KEYWORDS = {
    "screen": [("new kids movie", "en-au"), ("new animated family film", "en-au"),
               ("family film release", "en-au")],
}
GROUP_NAME = {"pressgang": "Press Gang News", "timeforkids": "TIME for Kids",
              "newsround": "Kid news", "science": "Science & space",
              "frontier": "Frontier tech", "screen": "Screen"}
PER_GROUP = {"frontier": 6, "science": 6, "screen": 4}
WANT_DEFAULT = 6

# sport: headline updates + junior achievements
TENNIS_FEEDS = ["https://www.tennismajors.com/feed/",
                "https://www.ubitennis.net/feed/",
                "https://tennishead.net/feed/",
                "https://lastwordonsports.com/tennis/feed/"]
SPORT_QUERIES = {
    "Coaching tips": [("tennis coaching drills", "en-au"), ("how to improve tennis forehand", "en-au"),
                      ("tennis technique tips", "en-au"), ("tennis training tips", "en-au")],
    "Junior stars (10-12)": [("junior tennis ranking Australia", "en-au"),
                             ("Australian junior tennis champion", "en-au"),
                             ("under 12 tennis Australia", "en-au"),
                             ("India junior tennis champion", "en-in")],
    "Basketball": [("basketball analysis tactics", "en-au"), ("NBL basketball", "en-au")],
    "Football": [("football tactics analysis", "en-au"), ("soccer match analysis", "en-au")],
}

APPLY = [
    (r"serve|ace|toss|first serve", "Serve: practise the toss 20 times before you hit a single serve. Steady toss, steady serve."),
    (r"return|returner", "Return: stand a step inside the baseline and split-step just as they toss."),
    (r"forehand", "Forehand: turn your shoulders early, then swing low to high and finish over your shoulder."),
    (r"backhand", "Backhand: get the racket back early, step in, and meet the ball out in front."),
    (r"volley|net play|at the net", "At the net: racket up and punch through the ball. Do not swing."),
    (r"drop shot|dropshot", "Drop shot: keep the same swing so they cannot read it, then soften your hands."),
    (r"slice|spin|topspin", "Spin: brush up the back of the ball. Watch how much it dips and kicks."),
    (r"footwork|movement|steps|split", "Footwork: take three small adjustment steps before every shot, then recover to the middle."),
    (r"fitness|injury|endurance|stamina|tired", "Fitness: finish every practice with five short sprints. Tired legs lose the last set."),
    (r"mental|nerve|pressure|comeback|tie-?break|choke|confidence", "Pressure: between points, turn away, breathe out slowly, say one word to yourself, then play fresh."),
    (r"tactic|strategy|pattern|plan", "Tactics: play three balls to their weaker side, then go the other way. Make them run."),
    (r"coach|training|practice", "Practice: pick ONE shot and do it slowly and correctly for ten minutes. Stop when you get tired."),
]


DEFAULT_TIPS = [
    "Watch one rally closely and count how many small steps the player takes before each shot.",
    "Pick one shot from this match and copy it in your next practice. Ten minutes, slowly.",
    "Notice where the player stands to return. Try standing a step inside next time you play.",
]


def apply_tip(title, paras=None):
    t = (title + " " + " ".join(paras or [])).lower()
    for pat, tip in APPLY:
        if re.search(pat, t):
            return tip
    return DEFAULT_TIPS[len(title) % len(DEFAULT_TIPS)]


BAD_OPEN = ("read more", "subscribe", "follow us", "click here", "sign up", "watch:",
            "just in case", "credit:", "getty", "photo:", "advertisement", "sponsored",
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


def ok(it, sport=False, screen=False):
    t = it["title"]
    if SPAM.search(t) or KID_BLOCK.search(t) or NO_THANKS.search(t):
        return False
    if FUNDRAISER.search(t):
        return False
    if sport and GOSSIP.search(t):
        return False
    if screen and SCREEN_BLOCK.search(t):
        return False
    return True


def score(it):
    t = it["title"]
    s = 2 if ENGAGE.search(t) else 0
    s -= 2 if DULL.search(t) else 0
    s -= 6 if CORP.search(t) else 0
    return s


def gather(urls, sport=False, screen=False):
    items, seen = [], set()
    for u in urls:
        try:
            got = parse(fetch_bytes(u))
        except Exception as ex:
            print("  ! fail", u, type(ex).__name__)
            continue
        print("  ok", len(got), u)
        for it in got:
            if not ok(it, sport=sport, screen=screen):
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
    "frontier": ["Which of these technologies would you most want to build?",
                 "What could go wrong with this, and how would you stop it?",
                 "How might this change life in India in ten years?"],
}


LLM_BASE = "https://text.pollinations.ai/"
LLM_SLEEP = 31          # the free endpoint allows about one reply every 30s
LLM_BUDGET = 10         # cap per run, so the job stays quick
_llm = {"n": 0}


def llm(prompt):
    """Ask a free language model to rewrite a story. Returns None on any failure."""
    if _llm["n"] >= LLM_BUDGET:
        return None
    _llm["n"] += 1
    try:
        req = urllib.request.Request(LLM_BASE + urllib.parse.quote(prompt),
                                     headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=75) as r:
            txt = r.read().decode("utf-8", "ignore").strip()
        low = txt.lower()
        if len(txt) > 60 and "free limit" not in low and "rate limit" not in low \
                and "payment required" not in low and not txt.startswith("{"):
            time.sleep(LLM_SLEEP)
            return txt
    except Exception as ex:
        print("  ! llm", type(ex).__name__)
    time.sleep(LLM_SLEEP)
    return None


def kid_prompt(age, title, text):
    return (
        "You write for a %d-year-old who lives in Melbourne, Australia and whose family is Indian. "
        "He is curious but has a short attention span.\n\n"
        "Rewrite the story below so that he understands EVERY sentence without needing any outside "
        "knowledge, and finishes curious.\n\n"
        "Hard rules:\n"
        "- Two short paragraphs, 70 to 95 words in total.\n"
        "- Every sentence must be 20 words or fewer. If a sentence runs longer, split it in two.\n"
        "- No jargon. If a technical word cannot be avoided, explain it in the same sentence, in "
        "plain words.\n"
        "- Never use an abbreviation without spelling it out (say 'the United Nations', not 'the UN').\n"
        "- Explain why it matters, so the story does not feel unfinished.\n"
        "- Then one final line of at most 15 words that makes him wonder. Begin that line with "
        "'Curious: '.\n"
        "- Use only facts from the story. Never invent names, numbers or quotes.\n"
        "- Warm, plain English. No emojis, no links, no headline, no bullet points.\n\n"
        "Before you answer, check your own work: would a 10-year-old who knows nothing about this "
        "understand every sentence? If not, rewrite that sentence. Then output only the final text.\n\n"
        "TITLE: %s\n\nSTORY: %s\n" % (age, title, text[:2400])
    )


def simpler_prompt(age, title, draft):
    return (
        "This text is for a %d-year-old and it is still too hard to read.\n\n"
        "Rewrite it so every sentence is 20 words or fewer, every hard word is explained in the "
        "same sentence, and no abbreviation is left unexplained. Keep two short paragraphs of 70 "
        "to 95 words, and keep the final 'Curious: ' line.\n\n"
        "TEXT:\n%s\n" % (age, draft[:1600])
    )


def clarity_ok(paras):
    """Nothing unclear ever reaches him. Returns (ok, reason)."""
    text = " ".join(paras).strip()
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if not sents:
        return False, "empty"
    words = sum(len(s.split()) for s in sents)
    if words < 55:
        return False, "too short (%d words)" % words
    if words > 115:
        return False, "too long (%d words)" % words
    longest = max(len(s.split()) for s in sents)
    if longest > 24:
        return False, "sentence of %d words" % longest
    mean = words / len(sents)
    if mean > 17:
        return False, "mean %.1f words per sentence" % mean
    if any(";" in s for s in sents):
        return False, "semicolon"
    if any(s.count(",") >= 4 for s in sents):
        return False, "run-on"
    if not re.search(r"\b(because|so that|which means|that is why|this means|as a result|"
                     r"so |that is because)\b", text, re.I):
        return False, "does not explain why"
    return True, ""


def parse_llm(out):
    curious = ""
    m = re.search(r"Curious:\s*(.+?)\s*$", out, re.I | re.S)
    if m:
        curious = re.sub(r"\s+", " ", m.group(1)).strip()
        out = out[:m.start()].strip()
    out = re.sub(r"```[a-z]*|```", "", out).strip()
    paras = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", out) if p.strip()]
    paras = [p for p in paras if len(p.split()) >= 8][:2]
    if not paras and out:
        paras = [out]
    return paras, curious[:170]


def rewrite(age, title, paras):
    """Rewrite with the model and hold it to the clarity gate.
    Returns (paras, curious, rewritten?)."""
    text = " ".join(paras)[:2600]
    short = simplify(paras, word_budget(age))
    if not text:
        return short, "", False
    out = llm(kid_prompt(age, title, text))
    if not out:
        return short, "", False
    lp, curious = parse_llm(out)
    ok, why = clarity_ok(lp)
    if not ok:
        print("  ~ clarity:", why, "-> retrying")
        out2 = llm(simpler_prompt(age, title, " ".join(lp)))
        if out2:
            lp2, c2 = parse_llm(out2)
            ok2, why2 = clarity_ok(lp2)
            if ok2:
                return lp2, c2, True
            print("  ~ clarity still failing:", why2)
        return short, "", False
    return lp, curious, True


SEEN_FILE = "spark-seen.json"
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


def fresh_first(items):
    """Drop anything shown in the last two months; reuse the oldest only if nothing is new."""
    fresh = [x for x in items if key_of(x["title"]) not in SEEN]
    if fresh:
        return fresh
    return sorted(items, key=lambda x: SEEN.get(key_of(x["title"]), 0))


def build_news(age, budget):
    news, seen, taken = [], set(), {}
    for g, feeds in FEEDS.items():
        urls = list(feeds) + [gn(q, l) for q, l in KEYWORDS.get(g, [])]
        items = gather(urls, screen=(g == "screen"))
        items = fresh_first(items)
        if g == "frontier":
            items.sort(key=lambda x: (5 if FRONTIER.search(x["title"]) else 0) + score(x), reverse=True)
        else:
            items.sort(key=score, reverse=True)
        print("GROUP", g, len(items))
        n = 0
        want = PER_GROUP.get(g, WANT_DEFAULT)
        fallback = []
        for it in items[:22]:
            if n >= want:
                break
            key = " ".join(it["title"].lower().split()[:4])
            if key in seen:
                continue
            paras = article_paragraphs(it["link"]) if it["link"].startswith("http") else []
            if not paras:
                paras = [it["desc"]] if it["desc"] else []
            short, curious, was_rewritten = rewrite(age, it["title"], paras)
            if sum(len(p.split()) for p in short) < MIN_WORDS:
                continue
            entry = {"kind": "news", "cat": g, "show": GROUP_NAME.get(g, g),
                     "title": it["title"][:110], "paras": short, "curious": curious,
                     "image": it["image"], "source": it["source"], "date": it["date"],
                     "link": it["link"]}
            if not was_rewritten:
                # hold it back: a raw extract is only used if the model gave us nothing
                fallback.append((key, entry))
                continue
            seen.add(key)
            mark_seen(it["title"])
            th = THINK.get(g, THINK["science"])
            entry["think"] = th[taken.get(g, 0) % len(th)]
            news.append(entry)
            taken[g] = taken.get(g, 0) + 1
            n += 1
        if n < want and fallback:
            # top up from the raw extracts so the shelf still holds a full row
            for key, entry in fallback:
                if n >= want:
                    break
                seen.add(key)
                mark_seen(entry["title"])
                th = THINK.get(g, THINK["science"])
                entry["think"] = th[taken.get(g, 0) % len(th)]
                news.append(entry)
                taken[g] = taken.get(g, 0) + 1
                n += 1
    return news


def build_analysis(age, budget):
    items = fresh_first(gather(TENNIS_FEEDS, sport=True))
    items.sort(key=lambda x: (1 if ANALYSIS.search(x["title"]) else 0, x["date"]), reverse=True)
    out, seen = [], set()
    for it in items[:12]:
        key = " ".join(it["title"].lower().split()[:4])
        if key in seen:
            continue
        paras = article_paragraphs(it["link"]) if it["link"].startswith("http") else []
        if not paras:
            paras = [it["desc"]] if it["desc"] else []
        short, curious, _rw = rewrite(age, it["title"], paras)
        if sum(len(p.split()) for p in short) < 28:
            continue
        seen.add(key)
        mark_seen(it["title"])
        out.append({"kind": "analysis", "section": "Match analysis", "title": it["title"][:110],
                    "paras": short, "curious": curious, "image": it["image"], "source": it["source"],
                    "date": it["date"], "link": it["link"], "apply": apply_tip(it["title"], short)})
        if len(out) >= 6:
            break
    print("ANALYSIS", len(out))
    return out


def build_sport(analysis):
    sport = list(analysis)
    sections = list(SPORT_QUERIES.items())
    for section, queries in sections:
        if False:
            pass
        else:
            items, seen = [], set()
            for q, lang in queries:
                try:
                    got = parse(fetch_bytes(gn(q, lang)))
                except Exception as ex:
                    print("  ! sport fail", q, type(ex).__name__)
                    continue
                for it in got:
                    if not ok(it, sport=True):
                        continue
                    k = it["title"].lower()
                    if k in seen:
                        continue
                    seen.add(k)
                    items.append(it)
        items.sort(key=lambda x: (1 if ANALYSIS.search(x["title"]) else 0, x["date"]), reverse=True)
        limit = 8 if section == "Match analysis" else 5
        for it in items[:limit]:
            sport.append({"kind": "head", "section": section, "title": it["title"][:110],
                          "source": it["source"], "date": it["date"], "link": it["link"]})
        print("SPORT", section, len(items))
    return sport


SCREEN_Q = [("new kids movie", "en-au"), ("new animated family film", "en-au"),
            ("family film release", "en-au"), ("new kids TV series", "en-au")]


def build_screen():
    items, seen = [], set()
    for q, lang in SCREEN_Q:
        try:
            got = parse(fetch_bytes(gn(q, lang)))
        except Exception as ex:
            print("  ! screen fail", q, type(ex).__name__)
            continue
        for it in got:
            if not ok(it, screen=True):
                continue
            k = it["title"].lower()
            if k in seen:
                continue
            seen.add(k)
            items.append(it)
    items.sort(key=lambda x: x["date"], reverse=True)
    print("SCREEN", len(items))
    return [{"kind": "head", "title": it["title"][:110], "source": it["source"],
             "date": it["date"]} for it in items[:6]]


def lint_library():
    """Report hand-written cards whose sentences are too long for a young reader."""
    try:
        data = json.load(open("spark_content.json", encoding="utf-8"))
    except Exception:
        return
    bad = []
    for t in data.get("topics", []):
        text = " ".join([t.get("hook", "")] + t.get("body", []))
        sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        longest = max((len(s.split()) for s in sents), default=0)
        if longest > 24:
            bad.append((longest, t.get("t", "?")))
    bad.sort(reverse=True)
    print("CLARITY LINT: %d cards have a sentence over 24 words" % len(bad))
    for w, ti in bad[:15]:
        print("   %2d words  %s" % (w, ti))


def main():
    age = age_now()
    gen = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("age", age)
    news = build_news(age, word_budget(age))
    sport = build_sport(build_analysis(age, word_budget(age)))
    screen = build_screen()
    os.makedirs("spark", exist_ok=True)
    with open(os.path.join("spark", "edition.json"), "w", encoding="utf-8") as f:
        json.dump({"generated": gen, "age": age, "news": news, "sport": sport,
                   "screen": screen}, f, ensure_ascii=False, separators=(",", ":"))
    save_seen()
    print("WROTE spark/edition.json:", len(news), "news |", len(sport), "sport |", len(screen), "screen",
          "| llm calls:", _llm["n"])


if __name__ == "__main__":
    main()
