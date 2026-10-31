#!/usr/bin/env python3
"""Can we pull a real, relevant photo for an article with no image? Test Wikipedia/Commons."""
import json
import re
import urllib.parse
import urllib.request

UA = ("PulseNewsBot/1.0 (personal news reader; contact akshay.bangalorekar@gmail.com)")

SAMPLES = [
    "Reserve Bank of India inflation",
    "Australian unemployment rate",
    "semiconductor factory India",
    "Shantadurga temple Goa",
    "Wimbledon tennis final",
    "Mumbai local train",
    "diwali faral sweets",
    "quantum computer",
]


def api(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def wiki_photo(term, size=800):
    u = ("https://en.wikipedia.org/w/api.php"
         "&gsrsearch=" + urllib.parse.quote(term) + "&gsrlimit=3&gsrnamespace=0"
         "&prop=pageimages&piprop=thumbnail|name&pithumbsize=" + str(size))
    try:
        d = api(u)
        pages = (d.get("query") or {}).get("pages") or {}
        best = None
        for p in pages.values():
            t = (p.get("thumbnail") or {}).get("source")
            if t:
                if best is None:
                    best = t
        return best
    except Exception as e:
        return "ERR:" + type(e).__name__


def commons_photo(term, size=800):
    u = ("https://commons.wikimedia.org/w/api.php"
         "&gsrsearch=" + urllib.parse.quote(term + " filetype:bitmap") + "&gsrlimit=3&gsrnamespace=6"
         "&prop=imageinfo&iiprop=url|mime&iiurlwidth=" + str(size))
    try:
        d = api(u)
        pages = (d.get("query") or {}).get("pages") or {}
        for p in pages.values():
            ii = (p.get("imageinfo") or [{}])[0]
            t = ii.get("thumburl") or ii.get("url")
            if t and not re.search(r"\.(svg|gif)$", t, re.I):
                return t
        return None
    except Exception as e:
        return "ERR:" + type(e).__name__


out = {}
for s in SAMPLES:
    w = wiki_photo(s)
    c = commons_photo(s)
    out[s] = {"wiki": w, "commons": c}
    print(f"{s[:34]:36s} wiki={'yes' if w and not str(w).startswith('ERR') else str(w)[:12]:6s} "
          f"commons={'yes' if c and not str(c).startswith('ERR') else str(c)[:12]}")
    if w and not str(w).startswith("ERR"):
        print("      ", w[:110])

json.dump(out, open("probe21.json", "w"), indent=1)
