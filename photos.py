#!/usr/bin/env python3
"""Real photographs for articles, from Wikipedia's free REST API.

No key, no cost. We map a headline to a Wikipedia subject, then take that
subject's lead photograph. Results are cached in photo-cache.json so a given
subject is fetched once, not once per build.
"""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

UA = "PulseNews/1.0 (https://github.com/akshaybangalorekar/pulse; akshay.bangalorekar@gmail.com)"
CACHE_FILE = "photo-cache.json"
TIMEOUT = 15

# headline pattern -> Wikipedia subject
TOPICS = [
    # money and macro
    (r"inflation|cost of living|price rise|महागाई", "Supermarket"),
    (r"unemploy|jobless|job market|hiring|payroll|नोकरी", "Job fair"),
    (r"reserve bank of india|\brbi\b|भारतीय रिझर्व्ह", "Reserve Bank of India"),
    (r"reserve bank of australia|\brba\b", "Reserve Bank of Australia"),
    (r"\basx\b|australian securities exchange|sharemarket|share market", "Australian Securities Exchange"),
    (r"sensex|nifty|stock market|stocks|equities|बाजार", "Stock exchange"),
    (r"\bgdp\b|gross domestic|economic growth", "Shopping mall"),
    (r"interest rate|rate cut|rate hike|monetary policy", "Bank branch"),
    (r"tariff|trade war|free trade|\bfta\b|export|import", "Container port"),
    (r"rupee|रुपया", "Bank branch"),
    (r"australian dollar|\baud\b", "Australian dollar"),
    (r"port|shipping|cargo|container", "Container port"),
    (r"semiconductor|chip maker|chipmaker|silicon|fab\b", "Integrated circuit"),
    (r"factory|manufactur|industrial production|उद्योग", "Assembly line"),
    (r"crude oil|opec|petrol|diesel|refinery|तेल", "Petroleum"),
    (r"natural gas|\blng\b", "Natural gas"),
    (r"solar|renewable|photovoltaic", "Solar panel"),
    (r"wind farm|wind power", "Wind turbine"),
    (r"electricity|power grid|blackout|ऊर्जा", "Power station"),
    (r"bank\b|banking|बँक", "Bank branch"),
    (r"insurance|बीमा", "Insurance"),
    (r"pension|superannuation|retirement", "Pension"),
    (r"tax|budget|gst", "Tax"),
    (r"housing|property price|real estate|rent", "Real estate"),
    (r"mining|iron ore|coal|lithium|rare earth|खनिज", "Mining"),
    (r"wheat|rice|crop|harvest|farmer|agricultur|शेतकरी", "Agriculture"),
    (r"monsoon|rainfall|flood|cyclone|पाऊस", "Monsoon"),
    # technology
    (r"artificial intelligence|\bai\b|machine learning|neural|chatbot|openai|chatgpt", "Artificial intelligence"),
    (r"quantum", "Quantum computing"),
    (r"robot|robotic|drone|automation", "Robot"),
    (r"cyber|hack|breach|malware|ransomware|data leak|सायबर", "Computer security"),
    (r"smartphone|iphone|android|mobile phone", "Smartphone"),
    (r"social media|tiktok|instagram|facebook|twitter|\bx\b app", "Smartphone"),
    (r"data cent|cloud comput|server", "Data center"),
    (r"bitcoin|crypto|blockchain", "Cryptocurrency"),
    (r"satellite|rocket|orbit|launch vehicle", "Satellite"),
    (r"isro|space research", "Indian Space Research Organisation"),
    (r"nasa|space telescope", "NASA"),
    (r"electric vehicle|\bev\b|battery", "Electric vehicle"),
    (r"nuclear", "Nuclear power"),
    # Bharat and its places
    (r"mumbai|bombay|मुंबई", "Mumbai"),
    (r"delhi|नवी दिल्ली", "New Delhi"),
    (r"bengaluru|bangalore|बंगळुरू", "Bangalore"),
    (r"pune|पुणे", "Pune"),
    (r"nagpur|nashik|thane|kolhapur|औरंगाबाद", "Maharashtra"),
    (r"\bgoa\b|panaji|panjim|margao|ponda|गोवा", "Goa"),
    (r"mangal|udupi|kundapur|karkala|uttara kannada|shirali|मंगळूर", "Mangalore"),
    (r"karnataka|कर्नाटक", "Karnataka"),
    (r"kerala|kochi|cochin|kanhangad|kasaragod", "Kerala"),
    (r"maharashtra|महाराष्ट्र", "Maharashtra"),
    (r"narendra modi|prime minister modi|मोदी", "Narendra Modi"),
    (r"parliament|lok sabha|rajya sabha|संसद", "Parliament of India"),
    (r"supreme court|high court|न्यायालय", "Supreme Court of India"),
    (r"election|विधानसभा|निवडणूक", "Election Commission of India"),
    # faith and culture
    (r"shantadurga|shanta durga|शांतादुर्गा", "Shanta Durga Temple"),
    (r"mangesh|manguesh|मंगेश", "Mangueshi Temple"),
    (r"kashi math|kashi mutt", "Kashi Math"),
    (r"chitrapur|shirali math", "Chitrapur Math"),
    (r"partagali|jeevottam", "Partagali Math"),
    (r"temple|devsthan|devasthan|मंदिर|देवस्थान", "Hindu temple"),
    (r"konkani|कोंकणी", "Goa"),
    (r"marathi|मराठी", "Maharashtra"),
    (r"saraswat", "Saraswat Brahmin"),
    (r"diwali|दिवाळी|deepavali", "Diwali"),
    (r"ganesh|ganpati|गणेश", "Ganesh Chaturthi"),
    (r"navratri|durga puja|दसरा", "Navaratri"),
    (r"holi|होळी", "Holi"),
    # sport
    (r"cricket|test match|\bodi\b|\bt20\b|आयपीएल", "Cricket"),
    (r"tennis|wimbledon|grand slam|australian open|\batp\b|\bwta\b", "Tennis"),
    (r"football|soccer|premier league|a-league|फुटबॉल", "Association football"),
    (r"hockey|ऑलिंपिक", "Field hockey"),
    (r"olympic|medal|athletics", "Olympic Games"),
    (r"badminton", "Badminton"),
    # screen, stage, music, food
    (r"bollywood|film|cinema|movie|actor|actress|चित्रपट", "Hindi cinema"),
    (r"marathi cinema|मराठी चित्रपट", "Marathi cinema"),
    (r"natak|theatre|theater|नाटक|रंगभूमी", "Theatre of India"),
    (r"serial|television|मालिका", "Television"),
    (r"music|song|concert|संगीत|गाणे", "Music of India"),
    (r"dance|नृत्य", "Dance in India"),
    (r"book|literature|poem|साहित्य", "Indian literature"),
    (r"recipe|food|faral|sweet|dish|पाककृती|फराळ", "Thali"),
    (r"stand-?up|comedy|विनोद|मस्करी", "Stand-up comedy"),
    (r"monster truck|monster jam", "Monster truck"),
]

# if a headline matches nothing, fall back to the section's subject
SECTION_SUBJECT = {
    "australia": "Melbourne", "bharat": "Gateway of India", "world": "Earth",
    "finance": "Stock exchange", "tech": "Artificial intelligence",
    "tennis": "Tennis", "football": "Association football",
    "indiasport": "Cricket", "marathi": "Maharashtra",
    "comedy": "Stand-up comedy", "monster": "Monster truck",
    "music": "Music of India", "parenting": "Family",
    "goa": "Goa", "mangalore": "Mangalore", "maths": "Hindu temple",
    "community": "Goa", "maharashtra": "Maharashtra",
    "natak": "Theatre of India", "serial": "Television",
    "gappa": "Hindi cinema", "faral": "Thali",
    "sant": "Diwali", "maskari": "Stand-up comedy", "anks": "Diwali",
    "pakkruti": "Thali",
    # spark shelves
    "current": "News", "frontier": "Robot", "science": "Outer space",
    "experiments": "Experiment", "thinking": "Thought", "sport": "Sport",
    "bharatiya": "Varanasi", "bharat_tech": "Bangalore",
    "friends": "Friendship", "creators": "Content creation",
    "games": "Video game", "aussie": "Melbourne", "trending": "Smartphone",
    "screen": "Film", "maths_magic": "Mathematics",
}

_cache = None

# charts, maps, logos and diagrams are not photographs
BAD_IMG = re.compile(r"(chart|graph|\bmap\b|diagram|logo|seal|emblem|coat_of_arms|"
                     r"plot|schematic|infographic|icon|\.png(\?|$))", re.I)


def upsize(url, width=900):
    """Wikimedia thumbnails come at ~330px; ask for a cover-sized version."""
    if not url:
        return url
    return re.sub(r"/(\d{2,4})px-", "/%dpx-" % width, url)


def load_cache():
    global _cache
    if _cache is None:
        try:
            _cache = json.load(open(CACHE_FILE, encoding="utf-8"))
        except Exception:
            _cache = {}
    return _cache


def save_cache():
    if _cache is None:
        return
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_cache, f, separators=(",", ":"), ensure_ascii=False)
    except Exception:
        pass


def wiki_photo(subject):
    """Lead photograph of a Wikipedia subject, or '' if there isn't a usable one."""
    cache = load_cache()
    if subject in cache:
        return cache[subject]
    url = ""
    try:
        api = ("https://en.wikipedia.org/api/rest_v1/page/summary/"
               + urllib.parse.quote(subject.replace(" ", "_")))
        req = urllib.request.Request(api, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            d = json.loads(r.read().decode("utf-8", "ignore"))
        url = ((d.get("thumbnail") or {}).get("source")
               or (d.get("originalimage") or {}).get("source") or "")
    except Exception:
        url = ""
    if re.search(r"\.(svg|gif)(\?|$)", url, re.I):
        url = ""                      # logos and maps make poor covers
    if url and BAD_IMG.search(url):
        url = ""                      # a chart or a map is not a photograph
    url = upsize(url)
    cache[subject] = url
    return url


def subject_for(title, section=""):
    t = title or ""
    for pat, subj in TOPICS:
        if re.search(pat, t, re.I):
            return subj
    return SECTION_SUBJECT.get(section or "", "")


def photo_for(title, section=""):
    """Best real photograph for this headline, or '' if none can be found."""
    subj = subject_for(title, section)
    if subj:
        ph = wiki_photo(subj)
        if ph:
            return ph
    # the headline's own subject gave us nothing usable - try the section's
    alt = SECTION_SUBJECT.get(section or "", "")
    if alt and alt != subj:
        return wiki_photo(alt)
    return ""


def backfill(items, section_of=lambda x: x.get("section", ""), title_of=lambda x: x.get("title", "")):
    """Give every item without a picture a real one."""
    n = 0
    for it in items:
        if it.get("image"):
            continue
        ph = photo_for(title_of(it), section_of(it))
        if ph:
            it["image"] = ph
            n += 1
    save_cache()
    return n
