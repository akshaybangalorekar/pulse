#!/usr/bin/env python3
"""Probe: can we call a language model from GitHub Actions with the built-in token?"""
import json
import os
import urllib.error
import urllib.request

TOKEN = os.environ.get("GITHUB_TOKEN", "")
print("token present:", bool(TOKEN), "len", len(TOKEN))

BODY = {
    "model": "openai/gpt-4o-mini",
    "messages": [{"role": "user",
                  "content": "Reply with exactly MODELS_OK, then one fun space fact for an 11 year old."}],
    "max_tokens": 60,
}


def call(url):
    req = urllib.request.Request(
        url, data=json.dumps(BODY).encode(),
        headers={"Authorization": "Bearer " + TOKEN,
                 "Content-Type": "application/json",
                 "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")
    except Exception as e:
        return "ERR", type(e).__name__ + ": " + str(e)


out = {}
for name, url in (("github_models", "https://models.github.ai/inference/chat/completions"),
                  ("azure", "https://models.inference.ai.azure.com/chat/completions")):
    st, body = call(url)
    out[name] = {"status": st, "body": body[:900]}
    print(name, st, body[:300])

json.dump(out, open("llm_out.json", "w"), indent=1)
