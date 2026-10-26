#!/usr/bin/env python3
"""Build the Marathi and Konkani editions of Pulse.

Marathi  : real Marathi sources only - the Maharashtra Times feed plus Marathi-language
           Google News searches. Nothing is translated from English.
Konkani  : community news searches plus hand-written cards on the maths and temples.
"""
import calendar
import html as htmlmod
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import feedparser

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")
TIMEOUT = 25
MIN_WORDS = 30

BAD = re.compile(r"(reels?\s*व्हिडिओ|जाहिरात|व्हिडिओ पहा|subscribe|advertisement|"
                 r"हत्या|खून|बलात्कार|अत्याचार|अपघात|मृत्यू|आत्महत्या|अंत्यविधी|"
                 r"पोलीस कोठडी|अटक)", re.I)
BOILER = re.compile(r"(आणखी वाचा|हेही वाचा|जाहिरात|सदस्यता|subscribe|also read|"
                    r"copyright|all rights reserved)", re.I)


def clean(s):
    if not s:
        return ""
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", htmlmod.unescape(s)).strip()


def get(url, accept="application/rss+xml, application/xml, text/html, */*"):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def gn(q, hl="mr", gl="IN", ceid="IN:mr"):
    return ("https://news.google.com/rss/search?q=" + urllib.parse.quote(q)
            + "&hl=" + hl + "&gl=" + gl + "&ceid=" + ceid)


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
                        "image": img if img.startswith("http") else "",
                        "date": ts, "desc": desc})
    return out


def sentences(text):
    # Marathi uses the danda as a full stop, so split on it too
    parts = re.split(r"(?<=[.!?\u0964])\s+", text)
    keep = []
    for s in parts:
        s = s.strip()
        if len(s.split()) < 5:
            continue
        if BOILER.search(s):
            continue
        keep.append(s)
    return keep


def condense(paras, budget=110):
    sents = []
    for p in paras:
        sents.extend(sentences(p))
    out, total = [], 0
    for s in sents:
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


def og_image(url):
    try:
        page = get(url, "text/html,*/*").decode("utf-8", "ignore")
    except Exception:
        return ""
    for pat in (r'property=["\']og:image["\'][^>]*content=["\']([^"\']+)',
                r'content=["\']([^"\']+)["\'][^>]*property=["\']og:image',
                r'name=["\']twitter:image["\'][^>]*content=["\']([^"\']+)'):
        m = re.search(pat, page, re.I)
        if m:
            u = m.group(1)
            if u.startswith("http"):
                return u
    return ""


def article_paras(url):
    try:
        txt = get(url, "text/html,*/*").decode("utf-8", "ignore")
    except Exception:
        return []
    txt = re.sub(r"(?is)<(script|style|noscript|nav|footer|aside)[^>]*>.*?</\1>", " ", txt)
    out = []
    for p in re.findall(r"(?is)<p[^>]*>(.*?)</p>", txt):
        c = clean(p)
        if len(c) > 60:
            out.append(c)
    return out


def gather(feeds, queries):
    items, seen = [], set()
    urls = list(feeds) + list(queries)
    for u in urls:
        try:
            got = parse(get(u))
        except Exception as ex:
            print("  !", u[:58], type(ex).__name__)
            continue
        for it in got:
            if BAD.search(it["title"]):
                continue
            k = it["title"].lower()
            if k in seen:
                continue
            seen.add(k)
            items.append(it)
    items.sort(key=lambda x: x["date"], reverse=True)
    return items


# ---------------------------------------------------------------- Marathi
MR_FEEDS = ["https://maharashtratimes.com/sitemap/rssfeed.xml"]
MR_QUERIES = [
    gn("महाराष्ट्र"),
    gn("मराठी नाटक"),
    gn("मराठी मालिका"),
    gn("मराठी चित्रपट"),
    gn("मस्करी विनोद"),
    gn("दिवाळी अंक"),
    gn("मराठी मासिक"),
    gn("चित्रलेखा मासिक"),
    gn("माहेर दिवाळी अंक"),
    gn("लोकप्रभा"),
    gn("साप्ताहिक सकाळ"),
    gn("दिवाळी फराळ"),
    gn("फराळ पदार्थ चकली अनारसे"),
    gn("दिवाळी सण परंपरा"),
    gn("मराठी अभिनेता मुलाखत"),
    gn("मराठी सेलिब्रिटी गप्पा"),
    gn("मराठी साहित्य संमेलन"),
    gn("पुणे मुंबई बातम्या"),
]

MR_SECTIONS = [
    {"id": "maharashtra", "name": "महाराष्ट्र", "emoji": "\U0001F5FE", "want": 6,
     "match": r"महाराष्ट्र|मुंबई|पुणे|नागपूर|ठाणे|कोल्हापूर|नाशिक|औरंगाबाद|छत्रपती|मराठा|विधानसभा|सरकार"},
    {"id": "natak", "name": "नाटक आणि रंगभूमी", "emoji": "\U0001F3AD", "want": 4,
     "match": r"नाटक|रंगभूमी|नाट्य|थिएटर|नाट्यसंमेलन|नाट्यस्पर्धा"},
    {"id": "serial", "name": "मालिका आणि मनोरंजन", "emoji": "\U0001F4FA", "want": 4,
     "match": r"मालिका|अभिनेता|अभिनेत्री|चित्रपट|मनोरंजन|झी मराठी|स्टार प्रवाह|सोनी मराठी|कलर्स मराठी"},
    {"id": "gappa", "name": "गप्पा मजा", "emoji": "\U0001F4AC", "want": 4,
     "match": r"मुलाखत|गप्पा|अभिनेता|अभिनेत्री|सेलिब्रिटी|कलाकार|दिग्दर्शक|निर्माता"},
    {"id": "faral", "name": "दिवाळी फराळ", "emoji": "\U0001F36A", "want": 4,
     "match": r"फराळ|चकली|अनारसे|शंकरपाळी|करंजी|चिवडा|लाडू|दिवाळी पदार्थ"},
    {"id": "sant", "name": "सण आणि परंपरा", "emoji": "\U0001F3EE", "want": 3,
     "match": r"दिवाळी|लक्ष्मीपूजन|भाऊबीज|नरकचतुर्दशी|गुडी पाडवा|गणेशोत्सव|नवरात्र|सण|उत्सव|परंपरा"},
    {"id": "maskari", "name": "मस्करी", "emoji": "\U0001F602", "want": 3,
     "match": r"मस्करी|विनोद|हास्य|ठिणगी|कॉमेडी|फनी"},
    {"id": "anks", "name": "दिवाळी अंक आणि मासिके", "emoji": "\U0001F4DA", "want": 5,
     "match": r"दिवाळी अंक|दिवाळीअंक|अंक|मासिक|मासिके|चित्रलेखा|माहेर|लोकप्रभा|साप्ताहिक|नियतकालिक"},
]

# hand-written Marathi recipes, always present
MR_RECIPES = [
    {"t": "चकली", "hook": "दिवाळीचा पहिला फराळ, आणि सर्वात आवडता.",
     "body": ["एक वाटी बेसन, दोन वाट्या तांदळाची पिठी, मीठ, तिखट, तीळ आणि गरम तेलाचा मोहरा एकत्र करा.",
              "पाणी घालून घट्ट कणीक मळा. चकलीच्या साच्यातून तव्यावर गोल आकारात पाडा.",
              "मंद आगीवर दोन्ही बाजूंनी खरपूस तळा. थंड झाल्यावर हवाबंद डब्यात ठेवा."],
     "wow": "चकली नीट शिजली की आवाज करते. म्हणूनच पुराण्या घरांत तिला 'खडक चकली' म्हणतात."},
    {"t": "अनारसे", "hook": "गोड आणि खमंग, दिवाळीची खासियत.",
     "body": ["तांदूळ भिजवून वाळवा आणि बारीक पिठी करा. गूळ पाण्यात वितळवून गाळून घ्या.",
              "पिठी, गूळाचा पाक, तीळ आणि वेलची एकत्र करून गुळगुळीत कणीक मळा.",
              "ओल्या कापडावर छोट्या पुऱ्या लाटा आणि मंद आगीवर तळा."],
     "wow": "अनारसे जास्त दिवस टिकतात, म्हणूनच दिवाळीत भेट म्हणून देण्याची प्रथा आहे."},
    {"t": "शंकरपाळी", "hook": "चहाबरोबर सर्वात जास्त चालणारा फराळ.",
     "body": ["मैदा, साखर, तूप, मीठ आणि दूध एकत्र करून कणीक मळा. अर्धा तास झाकून ठेवा.",
              "पुऱ्या लाटून चौकोनात कापा. मंद आगीवर सोनेरी रंग येईपर्यंत तळा.",
              "थंड झाल्यावर साखरेच्या पावडरमध्ये एकदा ढवळून घ्या."],
     "wow": "शंकरपाळीला इंग्रजीत 'diamond cuts' म्हणतात, कारण तिचा आकार हिऱ्यासारखा असतो."},
    {"t": "करंजी", "hook": "आत गोड, बाहेर खरपूस.",
     "body": ["मैदा, तूप आणि मीठ घेऊन कणीक मळा. ओल्या कापडाखाली ठेवा.",
              "सुकामेवा, खोबरे, गूळ आणि वेलचीचे सारण भाजून तयार करा.",
              "पुऱ्या लाटा, कडेला पाणी लावा, सारण भरा आणि चंद्रकोरीत बंद करा. मंद आगीवर तळा."],
     "wow": "करंजी महाराष्ट्रात 'करंजी' आहे, तर गुजरातेत ती 'घुघरा' म्हणून ओळखली जाते."},
    {"t": "पोहे चिवडा", "hook": "फराळात तिखटाची गरज भागवायला.",
     "body": ["पातळ पोहे कोरडे तळा आणि बाजूला ठेवा. शेंगदाणे आणि डाळही तळा.",
              "कढईत तेल गरम करा, मोहरी, जिरे, कढीपत्ता, हिरवी मिरची आणि आले घाला.",
              "हळद, मीठ, साखर आणि तिखट घाला. नंतर तळलेले पोहे आणि शेंगदाणे घालून मिसळा."],
     "wow": "चिवडा दिवाळीतलाच नाही, पुण्यात वर्षभर मिळतो. पण फराळात त्याला वेगळीच चव येते."},
]

MR_ANKS = [
    {"t": "दिवाळी अंक म्हणजे काय?", "hook": "दिवाळीच्या आधी येणारे खास वार्षिक अंक.",
     "body": ["दरवर्षी दिवाळीच्या आधी मराठी नियतकालिके आणि वर्तमानपत्रे 'दिवाळी अंक' काढतात. हा एक खास जाड, सणासुदीचा अंक असतो.",
              "यात कथा, कविता, ललित लेख, राजकीय विश्लेषण, व्यंगचित्रे आणि मुलांसाठीचे विभाग असतात. अनेक अंकांत एकही जाहिरात नसते.",
              "अनेक मराठी कुटुंबे हे अंक वर्षानुवर्षे जपून ठेवतात आणि पुन्हा वाचतात. त्यामुळे ते पुस्तकापेक्षा वाटून घेतलेली परंपरा वाटतात."],
     "wow": "काही दिवाळी अंक ३०० पेक्षा जास्त पानांचे असतात आणि त्यांची पहिली आवृत्ती आठवड्याभरात संपते."},
    {"t": "माहेर", "hook": "मराठी कुटुंबाचे जुने आणि आवडते मासिक.",
     "body": ["'माहेर' हे मराठीतले सर्वात जुन्या चालू असलेल्या कौटुंबिक मासिकांपैकी एक मानले जाते.",
              "त्याचा दिवाळी अंक विशेष लोकप्रिय आहे. त्यात कथा, कौटुंबिक लेख, वाचकांचे योगदान आणि सल्ला विभाग असतो.",
              "अनेकींसाठी माहेरचा अंक म्हणजे आईच्या घरची आठवण. तो वाचताना घरच्या गप्पा आठवतात, असे वाचक सांगतात."],
     "wow": "'माहेर' हे नाव 'माहेरची ओढ' या भावनेतून आले आहे, असे सांगितले जाते."},
    {"t": "चित्रलेखा", "hook": "बातमी आणि संस्कृती एकत्र.",
     "body": ["'चित्रलेखा' हे मराठीतले एक प्रसिद्ध मासिक आहे. ते बातम्या, मुलाखती आणि सांस्कृतिक लेख यासाठी ओळखले जाते.",
              "त्याचा दिवाळी अंक कथांसाठी, व्यंगचित्रांसाठी आणि चांगल्या छपाईसाठी बोलला जातो.",
              "अनेक वाचक दिवाळीच्या आठवड्यात माहेर, चित्रलेखा आणि लोकसत्तेचा अंक एकत्र घेतात."],
     "wow": "व्यंगचित्रांची परंपरा मराठी मासिकांनीच मोठी केली. अनेक नामवंत व्यंगचित्रकार याच अंकांतून पुढे आले."},
    {"t": "लोकप्रभा आणि साप्ताहिके", "hook": "आठवड्याचे वाचन, दिवाळीत जाड होऊन.",
     "body": ["'लोकप्रभा' हे लोकसत्ताचे साप्ताहिक आहे. ते राजकारण, अर्थ आणि समाज यावर लिखाण छापते.",
              "दिवाळीत अशी साप्ताहिके जाड, खास अंक काढतात. त्यात वर्षभराचा लेखाजोखा आणि मोठ्या मुलाखती असतात.",
              "आज अनेक अंक डिजिटलही येतात, पण कागदाच्या अंकाची चव वेगळीच असते."],
     "wow": "दिवाळी अंकांची बाजारपेठ महाराष्ट्रात इतकी मोठी आहे की अनेक प्रकाशक वर्षभर याच एका अंकाची तयारी करतात."},
    {"t": "मस्करीची परंपरा", "hook": "हसवणे ही पण एक कला आहे.",
     "body": ["मराठीत विनोदाची मोठी परंपरा आहे: विनोदी कविता, हास्यकवी संमेलने, व्यंगचित्रे आणि विनोदी सदरे.",
              "दिवाळी अंकात विनोदाला नेहमीच जागा असते. अनेक जण विनोदी लेखासाठीच अंक घेतात.",
              "मस्करी म्हणजे फक्त हसणे नाही. चांगला विनोद आपल्याला आपल्याकडेच हसायला शिकवतो."],
     "wow": "हास्यकवी संमेलने अजूनही महाराष्ट्रभर होतात आणि तिथे हजारो लोक जमतात."},
]

# ---------------------------------------------------------------- Konkani
KOK_QUERIES = [
    gn("Goa news", "en", "IN", "IN:en"),
    gn("Mangalore news", "en", "IN", "IN:en"),
    gn("Udupi Karnataka news", "en", "IN", "IN:en"),
    gn("Konkani", "en", "IN", "IN:en"),
    gn("Chitrapur Math Shirali", "en", "IN", "IN:en"),
    gn("Kashi Math Goud Saraswat", "en", "IN", "IN:en"),
    gn("Shantadurga Mangeshi temple", "en", "IN", "IN:en"),
    gn("Gaud Saraswat Brahmin", "en", "IN", "IN:en"),
    gn("Kanhangad Konkani", "en", "IN", "IN:en"),
    gn("Kochi Konkani community", "en", "IN", "IN:en"),
]
KOK_FEEDS = ["https://www.mangalorean.com/feed/"]

KOK_SECTIONS = [
    {"id": "goa", "name": "\u0917\u094b\u0935\u093e", "emoji": "\U0001F3D6", "want": 5,
     "match": r"goa|panaji|panjim|margao|ponda|vasco|mapusa|canacona"},
    {"id": "mangalore", "name": "\u092e\u0902\u0917\u0933\u0942\u0930 \u0906\u0923\u093f \u0915\u0930\u094d\u0928\u093e\u091f\u0915", "emoji": "\U0001F30A", "want": 5,
     "match": r"mangal|udupi|kundapur|karkala|uttara kannada|shirali|karwar|kanara|kanhangad|kasaragod"},
    {"id": "maths", "name": "\u092e\u0920 \u0906\u0923\u093f \u092e\u0902\u0926\u093f\u0930\u0947", "emoji": "\U0001F6D5", "want": 5,
     "match": r"math|shirali|chitrapur|kashi|partagali|jeevottam|shantadurga|mangesh|temple|swamiji"},
    {"id": "community", "name": "\u0938\u092e\u093e\u091c", "emoji": "\U0001F91D", "want": 5,
     "match": r"konkani|saraswat|gaud|gsb|community|kochi|kerala"},
]


def build_section(items, sec, used):
    out = []
    pat = re.compile(sec["match"], re.I)
    for it in items:
        if len(out) >= sec["want"]:
            break
        k = it["title"].lower()
        if k in used:
            continue
        if not pat.search(it["title"] + " " + it["desc"][:300]):
            continue
        paras = article_paras(it["link"]) if it["link"].startswith("http") else []
        if not paras:
            paras = [it["desc"]] if it["desc"] else []
        short = condense(paras)
        if sum(len(p.split()) for p in short) < MIN_WORDS:
            continue
        used.add(k)
        img = it["image"] or og_image(it["link"])
        out.append({"kind": "story", "title": it["title"][:120], "paras": short,
                    "image": img, "source": it["source"],
                    "link": it["link"], "date": it["date"]})
    return out


def main():
    gen = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ---- Marathi edition ----
    mr_items = gather(MR_FEEDS, MR_QUERIES)
    print("MR gathered:", len(mr_items))
    used = set()
    mr_sections = []
    for sec in MR_SECTIONS:
        got = build_section(mr_items, sec, used)
        print("  ", sec["id"], len(got))
        if got:
            mr_sections.append({"id": sec["id"], "name": sec["name"],
                                "emoji": sec["emoji"], "items": got})
    # recipes always present, hand-written
    mr_sections.append({"id": "pakkruti", "name": "पाककृती", "emoji": "\U0001F372",
                        "items": [{"kind": "card", "title": r["t"], "hook": r["hook"],
                                   "paras": r["body"], "wow": r["wow"]} for r in MR_RECIPES]})
    with open("pulse-mr.json", "w", encoding="utf-8") as f:
        json.dump({"generated": gen, "lang": "mr", "sections": mr_sections},
                  f, ensure_ascii=False, separators=(",", ":"))

    # ---- Konkani edition ----
    kok_items = gather(KOK_FEEDS, KOK_QUERIES)
    print("KOK gathered:", len(kok_items))
    used2 = set()
    kok_sections = []
    for sec in KOK_SECTIONS:
        got = build_section(kok_items, sec, used2)
        print("  ", sec["id"], len(got))
        if got:
            kok_sections.append({"id": sec["id"], "name": sec["name"],
                                 "emoji": sec["emoji"], "items": got})
    print("WROTE pulse-mr.json and pulse-kok.json")


if __name__ == "__main__":
    main()
