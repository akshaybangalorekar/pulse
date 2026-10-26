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

BAD = re.compile(r"(reels?\s*व्हिडिओ|जाहिरात|व्हिडिओ पहा|subscribe|advertisement)", re.I)
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
    gn("मराठी पाककृती रेसिपी"),
    gn("पुणे मुंबई बातम्या"),
]

MR_SECTIONS = [
    {"id": "maharashtra", "name": "महाराष्ट्र", "emoji": "\U0001F5FE", "want": 6,
     "match": r"महाराष्ट्र|मुंबई|पुणे|नागपूर|ठाणे|कोल्हापूर|नाशिक|औरंगाबाद|छत्रपती|मराठा|विधानसभा|सरकार"},
    {"id": "natak", "name": "नाटक आणि रंगभूमी", "emoji": "\U0001F3AD", "want": 4,
     "match": r"नाटक|रंगभूमी|नाट्य|थिएटर|नाट्यसंमेलन|नाट्यस्पर्धा"},
    {"id": "serial", "name": "मालिका आणि मनोरंजन", "emoji": "\U0001F4FA", "want": 4,
     "match": r"मालिका|अभिनेता|अभिनेत्री|चित्रपट|मनोरंजन|झी मराठी|स्टार प्रवाह|सोनी मराठी|कलर्स मराठी"},
    {"id": "maskari", "name": "मस्करी", "emoji": "\U0001F602", "want": 3,
     "match": r"मस्करी|विनोद|हास्य|ठिणगी|कॉमेडी|फनी"},
    {"id": "anks", "name": "दिवाळी अंक आणि मासिके", "emoji": "\U0001F4DA", "want": 5,
     "match": r"दिवाळी अंक|दिवाळीअंक|अंक|मासिक|मासिके|चित्रलेखा|माहेर|लोकप्रभा|साप्ताहिक|नियतकालिक"},
    {"id": "recipes", "name": "पाककृती", "emoji": "\U0001F372", "want": 4,
     "match": r"पाककृती|रेसिपी|पदार्थ|खाद्य|स्वयंपाक|पोहे|मिसळ|थालीपीठ|मोदक|पुरणपोळी"},
]

# hand-written Marathi recipes, always present
MR_RECIPES = [
    {"t": "कांदा पोहे", "hook": "मराठी घरातला सकाळचा आवडता नाश्ता.",
     "body": ["पोहे पाण्यात ५ मिनिटे भिजत ठेवा आणि नंतर पाणी पूर्ण निथळून टाका.",
              "कढईत तेल गरम करा. मोहरी, जिरे, कढीपत्ता आणि हिरवी मिरची घाला. नंतर बारीक चिरलेला कांदा आणि गाजर घालून परता.",
              "भिजलेले पोहे, मीठ आणि हळद घाला. २ मिनिटे ढवळा. वरून लिंबू आणि कोथिंबीर घालून सजवा."],
     "wow": "पोहे हा महाराष्ट्राचा नाश्ता आहे, पण आता तो जगभरच्या मराठी घरांत मिळतो."},
    {"t": "थालीपीठ", "hook": "एका तव्यावर संपूर्ण जेवण.",
     "body": ["बाजरी किंवा गव्हाचे पीठ, बारीक चिरलेला कांदा, कोथिंबीर, मेथी, मीठ आणि तिखट एकत्र मिसळा.",
              "पाणी घालून गुळगुळीत कणीक मळा. तवा गरम करा आणि हाताने कणीक पसरवा.",
              "दोन्ही बाजूंनी तूप घालून भाजा. वरून ताक किंवा लोणचे घालून खा."],
     "wow": "थालीपीठ हे मराठी घरांत 'भाजणी' च्या रूपात पिढ्यानपिढ्या चालत आले आहे."},
    {"t": "कोल्हापुरी तांबडा रस्सा", "hook": "तिखट, चटकदार आणि अगदी मराठमोळा.",
     "body": ["सुक्या खोबऱ्याचा, तिळाचा, मसाल्यांचा आणि कांद्याचा भाजलेला मसाला बारीक वाटा.",
              "कढईत तेल गरम करा, कांदा आणि आले-लसूण वाटण घाला. नंतर टोमॅटो आणि वाटलेला मसाला घाला.",
              "पाणी घालून उकळा. तयार रस्सा भात, भाकरी किंवा वड्याबरोबर खा."],
     "wow": "कोल्हापूरचा रस्सा तिखटाईसाठी प्रसिद्ध आहे. तिथे 'तांबडा रस्सा' हा स्वतंत्र पदार्थ म्हणूनच ओळखला जातो."},
    {"t": "श्रीखंड", "hook": "सणाच्या दिवशीची गोडी.",
     "body": ["दही चाळणीत बांधून रात्रभर टांगून ठेवा, जेणेकरून पाणी निघून जाईल.",
              "चक्का गुळगुळीत होईपर्यंत हलवा. त्यात साखर, वेलची पूड आणि केशर घाला.",
              "वरून सुकामेवा आणि आमच्या घरची आवडती बारीक चिरलेली फळे घालून थंड करा."],
     "wow": "श्रीखंड हे गुजरातच्या 'શ્રીખંડ' सारखेच आहे, पण महाराष्ट्रात ते विशेषतः गुढीपाडवा आणि दिवाळीला बनते."},
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
    gn("Chitrapur Math Shirali", "en", "IN", "IN:en"),
    gn("Kashi Math Goud Saraswat", "en", "IN", "IN:en"),
    gn("Partagali Jeevottam Math", "en", "IN", "IN:en"),
    gn("Shantadurga temple Goa", "en", "IN", "IN:en"),
    gn("Mangeshi temple Goa", "en", "IN", "IN:en"),
    gn("Konkani language", "en", "IN", "IN:en"),
    gn("Gaud Saraswat Brahmin community", "en", "IN", "IN:en"),
]

KOK_SECTIONS = [
    {"id": "maths", "name": "मठ", "emoji": "\U0001F6D5", "want": 5,
     "match": r"math|matha|shirali|chitrapur|kashi|partagali|jeevottam|swamiji|pontiff|sanyasi"},
    {"id": "temples", "name": "मंदिरे", "emoji": "\U0001F549", "want": 5,
     "match": r"temple|shantadurga|mangesh|manguesh|devsthan|devasthan|utsav|jatra|palkhi|festival"},
    {"id": "community", "name": "समाज", "emoji": "\U0001F91D", "want": 5,
     "match": r"saraswat|konkani|gaud|chitrapur|community|samaj|mangalore|udupi|kanhangad|kochi|goa"},
]

# hand-written Konkani-community cards (English; the app shows the Marathi/Konkani names)
KOK_CARDS = [
    {"t": "Shri Chitrapur Math, Shirali", "hook": "The spiritual home of the Chitrapur Saraswat community.",
     "body": ["The Shri Chitrapur Math is the math of the Chitrapur Saraswat Brahmin community. Its headquarters is at Shirali, in Uttara Kannada district of Karnataka.",
              "The community traces its roots to the Saraswat Brahmins who settled along the Kanara coast. The math has guided the community's religious and cultural life for generations, and runs schools, hostels and charitable work alongside its spiritual role.",
              "Its temples and shrines are cared for by the math, and the community gathers at Shirali through the year."],
     "wow": "The community's members are spread across Maharashtra, Karnataka, Goa and overseas, but Shirali remains the centre."},
    {"t": "Shrimad Partagali Jeevottam Math", "hook": "The Gaud Saraswat math in Goa.",
     "body": ["The Shrimad Partagali Jeevottam Math stands at Partagali in Canacona, south Goa, and is one of the principal maths of the Gaud Saraswat Brahmin community.",
              "It is named after Shrimad Jeevottam Teerth, and its deity is Shri Ramnath. The math has a long tradition of scholarship and of looking after temples in the region.",
              "Its annual festivals draw GSB families from Goa, Karnataka, Maharashtra and beyond."],
     "wow": "The Gaud Saraswat community is often called the GSB, and its maths in Goa and at Kashi are both central to its identity."},
    {"t": "Shri Kashi Math Samsthan", "hook": "A Konkani community's math, far away in Varanasi.",
     "body": ["The Shri Kashi Math Samsthan is a math of the Gaud Saraswat Brahmin community with its headquarters at Varanasi (Kashi).",
              "It traces its line of spiritual heads back centuries, and its branches and followers are spread through coastal Karnataka, Goa, Kerala and Maharashtra.",
              "The math runs temples, schools and charitable institutions, and its swamijis travel to the community's centres through the year."],
     "wow": "For a coastal community, having its math in Kashi is a reminder of how far Saraswat families travelled for scholarship."},
    {"t": "Shri Shantadurga Temple, Kavlem", "hook": "The goddess who is said to have settled a quarrel.",
     "body": ["The Shri Shantadurga temple at Kavlem in Ponda, Goa, is one of the most visited temples of the Gaud Saraswat community.",
              "The name Shantadurga means the goddess of peace. Tradition says she mediated between Shiva and Vishnu, and the temple's annual jatra is a major event in Goa.",
              "The present temple was built in the 18th century, after the original shrine was moved from its older site."],
     "wow": "Several Goan temples, including this one, were relocated inland in the 16th century to keep them safe."},
    {"t": "Shri Mangesh Temple, Priol", "hook": "A Shiva temple that belongs to the community.",
     "body": ["The Shri Mangesh temple at Priol (Mangeshi) in Ponda, Goa, is dedicated to Shiva and is closely tied to the Gaud Saraswat Brahmin community.",
              "The temple is known for its deepstambha, its tank and its distinctive Goan architecture, and its annual festivals draw large crowds.",
              "Like Shantadurga, the temple was moved to its present site in the 16th century."],
     "wow": "The Mangesh temple's architecture mixes Goan and Konkani styles, and it is one of the best-known temples in Goa."},
    {"t": "Konkani across four states", "hook": "One language, many coastlines.",
     "body": ["Konkani is spoken along the western coast, from Maharashtra through Goa and coastal Karnataka to northern Kerala.",
              "It is the official language of Goa and is written in Devanagari, though Roman script is also widely used by communities in Mangalore and Kochi.",
              "Konkani-speaking communities settled in Kanhangad in Kerala and in Kochi over centuries, and their temples and maths are still active today."],
     "wow": "Konkani was added to the Eighth Schedule of the Indian Constitution in 1992."},
    {"t": "The Saraswat thread", "hook": "Chitrapur and Gaud Saraswat are not the same community.",
     "body": ["The Konkani Saraswat world has two large branches: the Gaud Saraswat Brahmins and the Chitrapur Saraswats.",
              "The Gaud Saraswats are spread across Goa, coastal Karnataka and Kerala, and follow the Partagali and Kashi maths.",
              "The Chitrapur Saraswats are a smaller community centred on Shirali in Karnataka, with their own math and their own traditions."],
     "wow": "Both branches share the Konkani language and a coastal heritage, but their maths and customs are distinct."},
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
        out.append({"kind": "story", "title": it["title"][:120], "paras": short,
                    "image": it["image"], "source": it["source"],
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
    mr_sections.append({"id": "anksabout", "name": "दिवाळी अंक: परंपरा", "emoji": "\U0001F4D6",
                        "items": [{"kind": "card", "title": a["t"], "hook": a["hook"],
                                   "paras": a["body"], "wow": a["wow"]} for a in MR_ANKS]})
    mr_sections.append({"id": "pakkruti", "name": "पाककृती", "emoji": "\U0001F372",
                        "items": [{"kind": "card", "title": r["t"], "hook": r["hook"],
                                   "paras": r["body"], "wow": r["wow"]} for r in MR_RECIPES]})
    with open("pulse-mr.json", "w", encoding="utf-8") as f:
        json.dump({"generated": gen, "lang": "mr", "sections": mr_sections},
                  f, ensure_ascii=False, separators=(",", ":"))

    # ---- Konkani edition ----
    kok_items = gather([], KOK_QUERIES)
    print("KOK gathered:", len(kok_items))
    used2 = set()
    kok_sections = []
    for sec in KOK_SECTIONS:
        got = build_section(kok_items, sec, used2)
        print("  ", sec["id"], len(got))
        if got:
            kok_sections.append({"id": sec["id"], "name": sec["name"],
                                 "emoji": sec["emoji"], "items": got})
    kok_sections.append({"id": "about", "name": "मठ आणि मंदिरे", "emoji": "\U0001F6D5",
                         "items": [{"kind": "card", "title": c["t"], "hook": c["hook"],
                                    "paras": c["body"], "wow": c["wow"]} for c in KOK_CARDS]})
    with open("pulse-kok.json", "w", encoding="utf-8") as f:
        json.dump({"generated": gen, "lang": "kok", "sections": kok_sections},
                  f, ensure_ascii=False, separators=(",", ":"))

    print("WROTE pulse-mr.json and pulse-kok.json")


if __name__ == "__main__":
    main()
