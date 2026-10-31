#!/usr/bin/env python3
"""Which keyless image service actually responds from the runner?"""
import json
import urllib.error
import urllib.parse
import urllib.request

BROWSER = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/124 Safari/537.36")
BOT = "PulseNews/1.0 (https://github.com/akshaybangalorekar/pulse; akshay.bangalorekar@gmail.com)"

TESTS = {
    "wiki_api_botua": ("https://en.wikipedia.org/w/api.php"
                       "&titles=Reserve%20Bank%20of%20India&prop=pageimages&piprop=thumbnail"
                       "&pithumbsize=800", BOT),
    "wiki_api_browserua": ("https://en.wikipedia.org/w/api.php"
                           "&titles=Reserve%20Bank%20of%20India&prop=pageimages&piprop=thumbnail"
                           "&pithumbsize=800", BROWSER),
    "wiki_rest": ("https://en.wikipedia.org/api/rest_v1/page/summary/Reserve_Bank_of_India", BOT),
    "commons_api": ("https://commons.wikimedia.org/w/api.php"
                    "&titles=File:Reserve%20Bank%20of%20India%20logo.svg&prop=imageinfo"
                    "&iiprop=url&iiurlwidth=800", BOT),
    "upload_wikimedia": ("https://upload.wikimedia.org/wikipedia/commons/thumb/8/8b/"
                         "Reserve_Bank_of_India_Seal.svg/800px-Reserve_Bank_of_India_Seal.svg.png", BROWSER),
    "openverse": ("https://api.openverse.org/v1/images/", BROWSER),
    "pixabay_nokey": ("https://pixabay.com/api/", BROWSER),
    "pexels_nokey": ("https://api.pexels.com/v1/search", BROWSER),
    "wikimedia_commons_search": ("https://commons.wikimedia.org/w/index.php"
                                 "&title=Special:MediaSearch&type=image", BROWSER),
    "ddg_html": ("https://html.duckduckgo.com/html/", BROWSER),
}

out = {}
for name, (url, ua) in TESTS.items():
    rec = {}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=25) as r:
            body = r.read()
            rec["status"] = r.status
            rec["len"] = len(body)
            rec["head"] = body[:120].decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        rec["status"] = e.code
        rec["body"] = e.read()[:160].decode("utf-8", "ignore")
    except Exception as e:
        rec["error"] = type(e).__name__ + ": " + str(e)[:70]
    out[name] = rec
    print(f"{name:26s} {json.dumps(rec)[:170]}")

json.dump(out, open("probe22.json", "w"), indent=1)
