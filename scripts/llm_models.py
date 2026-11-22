"""Fallback model list for an OpenAI-compatible provider.

When the configured model is overloaded (HTTP 503/429) or times out, the
scripts try other fast text models from the provider's own /models list,
newest first, instead of giving up.
"""
import json
import os
import re
import urllib.request

SKIP = ("image", "tts", "audio", "live", "embedding", "vision", "robotics", "computer", "learnlm", "gemma", "aqa")


def _version(model_id):
    return [int(n) for n in re.findall(r"\d+", model_id)] or [0]


def fallback_models(current, limit=4):
    """Other 'flash' text models the key can list, newest first, excluding `current`."""
    base = os.environ["LLM_BASE_URL"].rstrip("/")
    key = os.environ["LLM_API_KEY"]
    current = (current or "").strip().removeprefix("models/")
    try:
        req = urllib.request.Request(base + "/models", headers={"Authorization": "Bearer " + key})
        with urllib.request.urlopen(req, timeout=30) as r:
            ids = [m["id"].removeprefix("models/") for m in json.load(r).get("data", [])]
    except Exception:
        return []
    cands = [i for i in ids if "flash" in i and i != current and not any(s in i for s in SKIP)]
    # same family first (e.g. the sibling "-lite" or a neighbouring version), then newest
    cands.sort(key=_version, reverse=True)
    return cands[:limit]
