"""Check the LLM_* secrets: list the models the key can use and run a tiny test.

Writes a readable result to the GitHub Actions job summary when run there.
"""
import json
import os
import sys
import urllib.error
import urllib.request

SUMMARY = os.environ.get("GITHUB_STEP_SUMMARY")


def say(line=""):
    print(line)
    if SUMMARY:
        with open(SUMMARY, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def request(url, key, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 method="POST" if body else "GET",
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def main():
    key, base, model = (os.environ.get(k, "").strip() for k in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"))
    say("## AI key check")
    missing = [n for n, v in (("LLM_API_KEY", key), ("LLM_BASE_URL", base)) if not v]
    if missing:
        say(f"❌ Missing secret(s): {', '.join(missing)}. Add them under Settings → Secrets and variables → Actions.")
        sys.exit(1)
    base = base.rstrip("/")

    try:
        ids = sorted(m["id"].removeprefix("models/") for m in request(base + "/models", key).get("data", []))
    except urllib.error.HTTPError as e:
        say(f"❌ The provider rejected the key or address (HTTP {e.code}). Check LLM_API_KEY and LLM_BASE_URL.")
        say(f"`{e.read().decode(errors='replace')[:300]}`")
        sys.exit(1)
    except Exception as e:
        say(f"❌ Couldn't reach {base}: {e}. Check LLM_BASE_URL.")
        sys.exit(1)
    say(f"✅ Key works. {len(ids)} models available.")
    fast = [i for i in ids if "flash" in i and not any(x in i for x in ("image", "tts", "audio", "live", "embedding", "thinking"))]
    if fast:
        say("Good choices for LLM_MODEL (fast, cheap): " + ", ".join(f"`{i}`" for i in fast[:8]))
    if not model:
        say("⚠️ LLM_MODEL is not set yet. Copy one name from the list above into the LLM_MODEL secret, then run this again.")
        sys.exit(1)
    if model.removeprefix("models/") not in ids:
        say(f"⚠️ `{model}` isn't in your key's model list. Pick one from the list above.")
    try:
        out = request(base + "/chat/completions", key, {"model": model, "messages": [
            {"role": "user", "content": "Write one short, friendly sentence about saving money. No hashtags."}]})
        say(f"✅ `{model}` replied: _{out['choices'][0]['message']['content'].strip()[:200]}_")
        say("All set: News tweets and the weekly drafts will now be written by AI.")
    except urllib.error.HTTPError as e:
        say(f"❌ `{model}` failed (HTTP {e.code}): `{e.read().decode(errors='replace')[:300]}`")
        sys.exit(1)


if __name__ == "__main__":
    main()
