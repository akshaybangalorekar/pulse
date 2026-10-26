#!/usr/bin/env python3
"""Discover real RSS endpoints for Marathi news sites and Konkani-community sites."""
import json
import re
import urllib.parse
import urllib.request

import feedparser

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")

HOMES = {
    "loksatta": "https://www.loksatta.com/",
    "lokmat": "https://www.lokmat.com/",
    "esakal": "https://www.esakal.com/",
    "divyamarathi": "https://divyamarathi.com/",
    "abpmajha": "https://marathi.abplive.com/",
    "maharashtratimes": "https://maharashtratimes.com/",
    "pudhari": "https://www.pudhari.news/",
    "daijiworld": "https://www.daijiworld.com/",
}


def get(url, accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.status, r.read().decode("utf-8", "ignore")


def candidates(html, base):
    found = []
    for m in re.finditer(r'<link[^>]+type=["\']application/(?:rss|atom)\+xml["\'][^>]*>', html, re.I):
        h = re.search(r'href=["\']([^"\']+)', m.group(0))
        if h:
            found.append(urllib.parse.urljoin(base, h.group(1)))
    for m in re.finditer(r'href=["\']([^"\']*(?:rss|/feed|feeds)[^"\']*)["\']', html, re.I):
        u = urllib.parse.urljoin(base, m.group(1))
        if u.startswith("http") and not re.search(r"facebook|twitter|instagram|youtube", u):
            found.append(u)
    seen, out = set(), []
    for u in found:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out[:12]


result = {}
for name, home in HOMES.items():
    rec = {"home": home, "candidates": [], "working": []}
    try:
        st, html = get(home)
        rec["status"] = st
        rec["len"] = len(html)
        cands = candidates(html, home)
        rec["candidates"] = cands
        for u in cands:
            try:
                st2, raw = get(u, "application/rss+xml, application/xml, */*")
                d = feedparser.parse(raw)
                if len(d.entries):
                    t = d.entries[0].get("title", "") or ""
                    rec["working"].append({
                        "url": u, "entries": len(d.entries), "sample": t[:50],
                        "devanagari": bool(re.search(r"[\u0900-\u097F]", t))})
            except Exception:
                pass
    except Exception as ex:
        rec["error"] = type(ex).__name__ + ": " + str(ex)[:70]
    result[name] = rec
    print("==", name, "| status", rec.get("status"), "| len", rec.get("len"), "| err", rec.get("error", ""))
    for w in rec["working"]:
        print("   WORKING:", w["url"][:80], "|", w["entries"], "| dev:", w["devanagari"], "|", w["sample"][:34])
    if not rec["working"]:
        for c in rec["candidates"][:6]:
            print("      cand:", c[:90])

json.dump(result, open("probe15.json", "w"), indent=1)
