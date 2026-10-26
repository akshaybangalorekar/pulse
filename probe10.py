#!/usr/bin/env python3
"""Discover the real RSS URLs for Swarajya, PTI and ANI from their homepages."""
import json
import re
import urllib.parse
import urllib.request

import feedparser

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")

HOMES = {
    "swarajya": "https://swarajyamag.com/",
    "pti": "https://www.ptinews.com/",
    "ani": "https://www.aninews.in/",
}


def get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.status, r.read().decode("utf-8", "ignore")


def candidates(html, base):
    found = []
    for m in re.finditer(r'<link[^>]+type=["\']application/(?:rss|atom)\+xml["\'][^>]*>', html, re.I):
        h = re.search(r'href=["\']([^"\']+)', m.group(0))
        if h:
            found.append(urllib.parse.urljoin(base, h.group(1)))
    for m in re.finditer(r'href=["\']([^"\']*(?:rss|feed|\.xml)[^"\']*)["\']', html, re.I):
        u = urllib.parse.urljoin(base, m.group(1))
        if u.startswith("http") and "facebook" not in u and "twitter" not in u:
            found.append(u)
    seen, out = set(), []
    for u in found:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out[:14]


result = {}
for name, home in HOMES.items():
    rec = {"home": home, "found": [], "working": []}
    try:
        st, html = get(home)
        rec["status"] = st
        rec["html_len"] = len(html)
        cands = candidates(html, home)
        rec["found"] = cands
        for u in cands:
            try:
                st2, raw = get(u)
                d = feedparser.parse(raw)
                if len(d.entries):
                    rec["working"].append({"url": u, "entries": len(d.entries),
                                           "sample": (d.entries[0].get("title", "") or "")[:60]})
            except Exception:
                pass
    except Exception as ex:
        rec["error"] = type(ex).__name__ + ": " + str(ex)[:80]
    result[name] = rec
    print("==", name, "==")
    print("   found:", len(rec.get("found", [])))
    for w in rec.get("working", []):
        print("   WORKING:", w["url"], "|", w["entries"], "entries |", w["sample"])

json.dump(result, open("probe10.json", "w"), indent=1)
