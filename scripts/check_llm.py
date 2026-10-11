"""Check the LLM_* secrets: find models that actually respond and test LLM_MODEL.

Providers list models in /models that new accounts can no longer use, so
this tries the fast candidates (newest first) and recommends only ones that
answer. Writes a readable result to the GitHub Actions job summary.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

SUMMARY = os.environ.get("GITHUB_STEP_SUMMARY")
SKIP = ("image", "tts", "audio", "live", "embedding", "thinking", "vision", "exp", "preview", "lite")


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


def version_key(model_id):
    """Sort newest first: gemini-3.8-flash before gemini-2.5-flash."""
    nums = [int(n) for n in re.findall(r"\d+", model_id)]
    return nums or [0]


def try_model(base, key, model):
    """Return (reply, None) on success or (None, error text)."""
    try:
        out = request(base + "/chat/completions", key, {"model": model, "messages": [
            {"role": "user", "content": "Write one short, friendly sentence about saving money. No hashtags."}]})
        return out["choices"][0]["message"]["content"].strip(), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.read().decode(errors='replace')[:400]}"
    except Exception as e:  # network or unexpected response
        return None, str(e)


def suggested_by(error):
    """Providers sometimes name the replacement model in the error message."""
    m = re.search(r"use (?:models/)?([A-Za-z0-9._-]+)", error or "")
    return m.group(1).rstrip(".") if m else None


def main():
    key, base, model = (os.environ.get(k, "").strip() for k in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"))
    model = model.removeprefix("models/")
    say("## AI key check")
    missing = [n for n, v in (("LLM_API_KEY", key), ("LLM_BASE_URL", base)) if not v]
    if missing:
        say(f"❌ Missing secret(s): {', '.join(missing)}. Add them under Settings → Secrets and variables → Actions.")
        sys.exit(1)
    base = base.rstrip("/")

    try:
        ids = [m["id"].removeprefix("models/") for m in request(base + "/models", key).get("data", [])]
    except urllib.error.HTTPError as e:
        say(f"❌ The provider rejected the key or address (HTTP {e.code}). Check LLM_API_KEY and LLM_BASE_URL.")
        say(f"`{e.read().decode(errors='replace')[:300]}`")
        sys.exit(1)
    except Exception as e:
        say(f"❌ Couldn't reach {base}: {e}. Check LLM_BASE_URL.")
        sys.exit(1)
    say(f"✅ Key works ({len(ids)} models listed).")

    if model:
        reply, err = try_model(base, key, model)
        if reply:
            say(f"✅ `{model}` replied: _{reply[:200]}_")
            say("All set: News tweets and the weekly drafts will be written by AI.")
            return
        say(f"❌ `{model}` didn't work: `{err}`")
    else:
        say("⚠️ LLM_MODEL is not set yet.")
        err = None

    # Find models that actually answer: the provider's own suggestion first,
    # then fast models from the list, newest first.
    candidates = []
    hint = suggested_by(err)
    if hint:
        candidates.append(hint)
    fast = sorted((i for i in ids if "flash" in i and not any(x in i for x in SKIP)), key=version_key, reverse=True)
    candidates += [c for c in fast if c not in candidates]
    working = []
    for c in candidates[:5]:
        reply, _ = try_model(base, key, c)
        if reply:
            working.append(c)
            if len(working) == 2:
                break
    if working:
        say(f"👉 Set the **LLM_MODEL** secret to **`{working[0]}`** (tested and working), then run Test AI key again.")
        if len(working) > 1:
            say(f"Also works: `{working[1]}`")
    else:
        say("❌ None of the fast models answered. Check the key's limits in your provider's dashboard, or pick a model from its docs.")
    sys.exit(1)


if __name__ == "__main__":
    main()
