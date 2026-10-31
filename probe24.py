#!/usr/bin/env python3
"""Direct Wikipedia REST summary lookups - do these return real photos?"""
import json
import urllib.error
import urllib.parse
import urllib.request

BOT = "PulseNews/1.0 (https://github.com/akshaybangalorekar/pulse; akshay.bangalorekar@gmail.com)"

TITLES = [
    "Reserve Bank of India", "Inflation", "Unemployment", "Semiconductor",
    "Shanta Durga Temple", "The Championships, Wimbledon", "Mumbai",
    "Diwali", "Quantum computing", "Kashi Math", "Mangalore", "Konkani language",
    "Goa", "Cricket", "Australian Securities Exchange", "Narendra Modi",
    "Artificial intelligence", "Tata Group", "Shivaji", "Sari",
]


def photo(title, size=900):
    u = ("https://en.wikipedia.org/api/rest_v1/page/summary/"
         + urllib.parse.quote(title.replace(" ", "_")))
    req = urllib.request.Request(u, headers={"User-Agent": BOT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            d = json.loads(r.read().decode("utf-8", "ignore"))
        th = (d.get("thumbnail") or {}).get("source")
        orig = (d.get("originalimage") or {}).get("source")
        return th or orig
    except urllib.error.HTTPError as e:
        return "HTTP" + str(e.code)
    except Exception as e:
        return "ERR:" + type(e).__name__


out = {}
ok = 0
for t in TITLES:
    p = photo(t)
    good = bool(p) and not str(p).startswith(("HTTP", "ERR"))
    if good:
        ok += 1
    out[t] = p
    print(f"{'PHOTO' if good else 'none ':6s} {t[:34]:36s} {str(p)[:78]}")

print(f"\n{ok}/{len(TITLES)} resolved to a real photo")
json.dump(out, open("probe24.json", "w"), indent=1)
