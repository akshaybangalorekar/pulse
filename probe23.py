#!/usr/bin/env python3
"""Can we search Wikipedia by keyword and get a real photo, all through REST?"""
import json
import urllib.error
import urllib.parse
import urllib.request

BOT = "PulseNews/1.0 (https://github.com/akshaybangalorekar/pulse; akshay.bangalorekar@gmail.com)"

QUERIES = [
    "Reserve Bank of India", "inflation", "unemployment Australia", "semiconductor",
    "Shantadurga temple", "Wimbledon", "Mumbai", "Diwali", "quantum computing",
    "Kashi Math", "Mangalore", "Konkani language",
]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": BOT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def search_title(q):
    u = ("https://en.wikipedia.org/w/rest.php/v1/search/page"
         + urllib.parse.quote(q) + "&limit=3")
    try:
        d = get(u)
        pages = d.get("pages") or []
        return [p.get("title") for p in pages if p.get("title")]
    except urllib.error.HTTPError as e:
        return ["HTTP" + str(e.code)]
    except Exception as e:
        return ["ERR:" + type(e).__name__]


def photo(title):
    u = ("https://en.wikipedia.org/api/rest_v1/page/summary/"
         + urllib.parse.quote(title.replace(" ", "_")))
    try:
        d = get(u)
        th = (d.get("thumbnail") or {}).get("source")
        return th
    except urllib.error.HTTPError as e:
        return "HTTP" + str(e.code)
    except Exception as e:
        return "ERR:" + type(e).__name__


out = {}
for q in QUERIES:
    titles = search_title(q)
    best = None
    for t in titles[:3]:
        if t.startswith("HTTP") or t.startswith("ERR"):
            continue
        ph = photo(t)
        if ph and not str(ph).startswith(("HTTP", "ERR")):
            best = {"title": t, "photo": ph}
            break
    out[q] = {"titles": titles[:3], "best": best}
    print(f"{q[:26]:28s} -> {str(best)[:120]}")

json.dump(out, open("probe23.json", "w"), indent=1)
