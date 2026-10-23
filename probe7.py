#!/usr/bin/env python3
import urllib.parse
"""Try to find a keyless / token-based LLM reachable from the runner."""
import json
import os
import urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
PROMPT = "In one short sentence a 10-year-old would understand: what is a qubit?"
out = {}


def try_get(name, url, headers=None):
    try:
        req = urllib.request.Request(url, headers=headers or {"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=45) as r:
            body = r.read(1500).decode("utf-8", "ignore")
        out[name] = {"status": r.status, "body": body[:400]}
    except Exception as e:
        out[name] = {"error": type(e).__name__ + ": " + str(e)[:160]}


def try_post(name, url, payload, headers):
    try:
        data = json.dumps(payload).encode()
        h = {"Content-Type": "application/json", "User-Agent": UA}
        h.update(headers or {})
        req = urllib.request.Request(url, data=data, headers=h)
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read(2500).decode("utf-8", "ignore")
        out[name] = {"status": r.status, "body": body[:700]}
    except Exception as e:
        detail = ""
        try:
            detail = e.read(300).decode("utf-8", "ignore")
        except Exception:
            pass
        out[name] = {"error": type(e).__name__ + ": " + str(e)[:120], "detail": detail[:300]}


# 1. Pollinations simple GET
try_get("pollinations_get", "https://text.pollinations.ai/" + urllib.parse.quote(PROMPT))

# 2. Pollinations OpenAI-compatible POST
try_post("pollinations_openai", "https://text.pollinations.ai/openai",
         {"model": "openai", "messages": [{"role": "user", "content": PROMPT}], "max_tokens": 80},
         {})

# 3. GitHub Models (runner has GITHUB_TOKEN)
tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
if tok:
    try_post("github_models", "https://models.github.ai/inference/chat/completions",
             {"model": "openai/gpt-4o-mini",
              "messages": [{"role": "user", "content": PROMPT}], "max_tokens": 80},
             {"Authorization": "Bearer " + tok})
else:
    out["github_models"] = {"error": "no GITHUB_TOKEN in env"}

json.dump(out, open("probe7.json", "w"), indent=1)
print(json.dumps(out, indent=1))
