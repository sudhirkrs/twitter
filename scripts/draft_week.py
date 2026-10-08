"""Draft the next 7 days of posts with an AI model and add them to the queue as drafts.

Works with any OpenAI-compatible chat API (Google Gemini, Groq, OpenRouter,
OpenAI, a local model...). Configure with environment variables:

    LLM_API_KEY    API key for the provider
    LLM_BASE_URL   e.g. https://generativelanguage.googleapis.com/v1beta/openai
    LLM_MODEL      a model name your provider offers

New posts get "status": "draft". They show up in the Control Panel for
review and get no "Open in X" link until approved.

Usage:
    python scripts/draft_week.py            # draft if fewer than 14 days are queued ahead
    python scripts/draft_week.py --force    # draft 7 more days regardless
    python scripts/draft_week.py --dry-run  # print the prompt, call nothing
"""
import argparse
import csv
import json
import os
import re
import sys
import urllib.request
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from poster import QUEUE_FILE, check, load_queue, tweet_weight  # noqa: E402

METRICS_FILE = ROOT / "tracking" / "post-metrics.csv"
DAYS_PER_DRAFT = 7
MAX_AHEAD = 14
ATTEMPTS = 3

SYSTEM_PROMPT = """You write X (Twitter) posts for @Sudhirkrs17, an Indian creator who explains
how money works: personal finance first, then payments and fintech, AI and money, and books.
Audience: salaried Indians aged 22-40. Voice: clear, practical, friendly, no jargon, no hype.

Hard rules:
- Every tweet (each thread part, each poll question) must be at most 270 characters.
  Emoji, ₹, •, → count double, so use them sparingly.
- Line 1 is a hook: a number, a surprise or a stake.
- Use specific numbers only when they are simple, well-known or computable from the post
  itself (e.g. SIP or EMI maths). Never invent statistics, dates, rules or quotes. If unsure
  of a regulation's current details, describe it generally.
- No stock tips, no "guaranteed returns", no investment recommendations for specific securities.
- No links. No hashtags.
- Do not repeat topics or hooks from the recent posts you are given.
- Thread final parts end with: Follow @Sudhirkrs17 for ...

Mix for the 14 posts (7 days x am/pm):
- 7 personal-finance, 3 payments or fintech, 2 ai, 2 books (approximately)
- 3 threads of 5-7 parts (mornings), 1 poll, 2-3 engagement questions, the rest single tweets.

Return ONLY a JSON object, no commentary:
{"posts": [{"day": <int>, "slot": "am"|"pm",
            "pillar": "personal-finance"|"payments"|"fintech"|"ai"|"books"|"engagement",
            "type": "tweet"|"thread"|"poll",
            "parts": ["tweet 1", "tweet 2", ...],
            "poll": {"options": ["<=25 chars", ...2-4 items], "duration_minutes": 1440}  (polls only)
           }, ...]}
Single tweets and polls have exactly one part."""


def today_ist(queue):
    return datetime.now(ZoneInfo(queue["timezone"])).date()


def engagement_rate(row):
    views = int(row.get("views") or 0)
    if views <= 0:
        return 0.0
    score = sum(int(row.get(k) or 0) for k in ("likes",)) + 2 * sum(
        int(row.get(k) or 0) for k in ("replies", "reposts", "bookmarks"))
    return score / views


def top_posts(queue, n=5):
    if not METRICS_FILE.exists():
        return []
    by_id = {p["id"]: p for p in queue["posts"]}
    rows = [r for r in csv.DictReader(METRICS_FILE.open(encoding="utf-8")) if r.get("post_id") in by_id]
    rows.sort(key=engagement_rate, reverse=True)
    out = []
    for r in rows[:n]:
        p = by_id[r["post_id"]]
        out.append({"pillar": p["pillar"], "type": p["type"], "views": r.get("views"),
                    "engagement_rate": round(engagement_rate(r), 4), "first_tweet": p["parts"][0]})
    return out


def build_messages(queue, first_day):
    days = list(range(first_day, first_day + DAYS_PER_DRAFT))
    recent = [p["parts"][0].splitlines()[0] for p in queue["posts"][-40:]]
    best = top_posts(queue)
    user = {
        "days_to_write": days,
        "slots": {"am": queue["slots"]["am"] + " IST", "pm": queue["slots"]["pm"] + " IST"},
        "recent_hooks_do_not_repeat": recent,
        "best_performing_posts_write_more_like_these": best or "no metrics yet",
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Write the posts for these days.\n" + json.dumps(user, ensure_ascii=False, indent=1)},
    ]


def call_llm(messages):
    base = os.environ["LLM_BASE_URL"].rstrip("/")
    body = json.dumps({"model": os.environ["LLM_MODEL"], "messages": messages, "temperature": 0.8}).encode()
    req = urllib.request.Request(
        base + "/chat/completions", data=body, method="POST",
        headers={"Authorization": "Bearer " + os.environ["LLM_API_KEY"], "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.load(resp)
    return data["choices"][0]["message"]["content"]


def parse_posts(text):
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError("no JSON object in the response")
    return json.loads(match.group(0))["posts"]


def validate(queue, posts, days):
    errors = []
    want = {(d, s) for d in days for s in ("am", "pm")}
    got = set()
    for p in posts:
        key = (p.get("day"), p.get("slot"))
        if key not in want:
            errors.append(f"unexpected day/slot {key}")
        elif key in got:
            errors.append(f"duplicate day/slot {key}")
        got.add(key)
        for i, part in enumerate(p.get("parts") or [], 1):
            if tweet_weight(part) > 280:
                errors.append(f"day {key[0]} {key[1]} part {i} is {tweet_weight(part)} weighted chars (max 280)")
    missing = want - got
    if missing:
        errors.append(f"missing day/slots {sorted(missing)}")
    if not errors:
        trial = dict(queue, posts=queue["posts"] + [normalise(p) for p in posts])
        errors += check(trial)
    return errors


def normalise(p):
    item = {"id": f"d{p['day']:02d}-{p['slot']}", "day": p["day"], "slot": p["slot"],
            "pillar": p.get("pillar", "personal-finance"), "type": p["type"],
            "parts": [s.strip() for s in p["parts"]], "status": "draft"}
    if p["type"] == "poll":
        item["poll"] = {"options": p["poll"]["options"], "duration_minutes": int(p["poll"].get("duration_minutes", 1440))}
    return item


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    queue = load_queue()
    start = date.fromisoformat(queue["start_date"])
    last_day = max(p["day"] for p in queue["posts"])
    today_num = (today_ist(queue) - start).days + 1
    if not args.force and last_day - today_num >= MAX_AHEAD:
        print(f"Queue already runs {last_day - today_num} days ahead; nothing to draft.")
        return
    first = last_day + 1
    days = list(range(first, first + DAYS_PER_DRAFT))
    messages = build_messages(queue, first)
    if args.dry_run:
        print(json.dumps(messages, ensure_ascii=False, indent=1))
        return
    for k in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        if not os.environ.get(k):
            sys.exit(f"Missing environment variable {k}. See README: Weekly AI drafts.")

    for attempt in range(1, ATTEMPTS + 1):
        reply = call_llm(messages)
        try:
            posts = parse_posts(reply)
            errors = validate(queue, posts, days)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
            errors = [f"could not read the response: {e}"]
        if not errors:
            break
        print(f"Attempt {attempt}: {len(errors)} problem(s): {errors[:5]}")
        messages += [{"role": "assistant", "content": reply},
                     {"role": "user", "content": "Fix these problems and return the full JSON again:\n- " + "\n- ".join(errors)}]
    else:
        sys.exit("The model did not return valid posts after several attempts.")

    new = sorted((normalise(p) for p in posts), key=lambda p: (p["day"], p["slot"]))
    queue["posts"] += new
    QUEUE_FILE.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    first_date = start.toordinal() + first - 1
    print(f"Drafted {len(new)} posts for days {days[0]}-{days[-1]} "
          f"(from {date.fromordinal(first_date):%a %d %b}).")


if __name__ == "__main__":
    main()
