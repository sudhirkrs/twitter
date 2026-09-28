"""Post scheduled content from content/queue.json to X (Twitter).

Usage:
    python poster.py --check          # validate every post (length, structure)
    python poster.py --list           # show the schedule and what's been posted
    python poster.py --dry-run        # print what would be posted now, post nothing
    python poster.py                  # post due items (needs X_* env vars)

Credentials come from environment variables:
    X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET
"""
import argparse
import json
import os
import sys
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
QUEUE_FILE = ROOT / "content" / "queue.json"
STATE_FILE = ROOT / "state" / "posted.json"
MAX_WEIGHT = 280
# Don't post items that were due more than this long ago (e.g. after a long outage).
STALE_AFTER = timedelta(hours=36)

# X counts characters in these code point ranges as 1; everything else
# (including emoji, ₹, •, →) counts as 2. See twitter-text config v3.
LIGHT_RANGES = [(0, 4351), (8192, 8205), (8208, 8223), (8242, 8247)]


def tweet_weight(text):
    text = unicodedata.normalize("NFC", text)
    weight = 0
    for ch in text:
        cp = ord(ch)
        weight += 1 if any(lo <= cp <= hi for lo, hi in LIGHT_RANGES) else 2
    return weight


def load_queue():
    return json.loads(QUEUE_FILE.read_text(encoding="utf-8"))


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state):
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def scheduled_at(queue, post):
    tz = ZoneInfo(queue["timezone"])
    start = datetime.fromisoformat(queue["start_date"]).date()
    hh, mm = map(int, queue["slots"][post["slot"]].split(":"))
    day = start + timedelta(days=post["day"] - 1)
    return datetime(day.year, day.month, day.day, hh, mm, tzinfo=tz)


def is_done(state, post):
    entry = state.get(post["id"])
    return bool(entry) and len(entry.get("tweet_ids", [])) >= len(post["parts"])


def check(queue):
    errors = []
    seen = set()
    for post in queue["posts"]:
        pid = post["id"]
        if pid in seen:
            errors.append(f"{pid}: duplicate id")
        seen.add(pid)
        if post["slot"] not in queue["slots"]:
            errors.append(f"{pid}: unknown slot {post['slot']!r}")
        if not post["parts"]:
            errors.append(f"{pid}: no parts")
        for i, part in enumerate(post["parts"], 1):
            w = tweet_weight(part)
            if w > MAX_WEIGHT:
                errors.append(f"{pid} part {i}: {w}/{MAX_WEIGHT} weighted chars")
        if post["type"] == "poll":
            opts = post.get("poll", {}).get("options", [])
            if not 2 <= len(opts) <= 4 or any(len(o) > 25 for o in opts):
                errors.append(f"{pid}: poll needs 2-4 options of <=25 chars")
            if len(post["parts"]) != 1:
                errors.append(f"{pid}: poll must be a single tweet")
    return errors


def make_client():
    import tweepy

    keys = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]
    missing = [k for k in keys if not os.environ.get(k)]
    if missing:
        sys.exit(f"Missing environment variables: {', '.join(missing)}")
    return tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )


def publish(client, post, state):
    """Post every not-yet-posted part of `post`, resuming a partial thread."""
    entry = state.setdefault(post["id"], {"tweet_ids": []})
    ids = entry["tweet_ids"]
    for i in range(len(ids), len(post["parts"])):
        kwargs = {"text": post["parts"][i]}
        if ids:
            kwargs["in_reply_to_tweet_id"] = ids[-1]
        if post["type"] == "poll":
            kwargs["poll_options"] = post["poll"]["options"]
            kwargs["poll_duration_minutes"] = post["poll"]["duration_minutes"]
        resp = client.create_tweet(**kwargs)
        ids.append(resp.data["id"])
        entry["posted_at"] = datetime.now(ZoneInfo("UTC")).isoformat(timespec="seconds")
        save_state(state)  # persist after each part so a crash can resume
        print(f"  posted {post['id']} part {i + 1}/{len(post['parts'])}: {resp.data['id']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="validate the queue and exit")
    ap.add_argument("--list", action="store_true", help="print the schedule and exit")
    ap.add_argument("--dry-run", action="store_true", help="show what would post; post nothing")
    ap.add_argument("--max", type=int, default=1, help="max items to post this run (default 1)")
    ap.add_argument("--now", help="override current time (ISO 8601), for testing")
    args = ap.parse_args()

    queue = load_queue()
    errors = check(queue)
    if errors:
        print("Queue has problems:\n  " + "\n  ".join(errors))
        sys.exit(1)
    if args.check:
        print(f"OK: {len(queue['posts'])} posts valid.")
        return

    state = load_state()
    now = datetime.fromisoformat(args.now) if args.now else datetime.now(ZoneInfo("UTC"))
    posts = sorted(queue["posts"], key=lambda p: scheduled_at(queue, p))

    if args.list:
        for p in posts:
            mark = "✓" if is_done(state, p) else " "
            first = p["parts"][0].splitlines()[0][:60]
            print(f"[{mark}] {scheduled_at(queue, p):%a %d %b %H:%M}  {p['id']:<8} {p['type']:<6} {first}")
        return

    due = [p for p in posts if not is_done(state, p) and scheduled_at(queue, p) <= now]
    stale = [p for p in due if now - scheduled_at(queue, p) > STALE_AFTER]
    due = [p for p in due if p not in stale][: args.max]
    for p in stale:
        print(f"Skipping stale item {p['id']} (was due {scheduled_at(queue, p):%d %b %H:%M}).")

    if not due:
        print("Nothing due.")
        return

    if args.dry_run:
        for p in due:
            print(f"--- would post {p['id']} ({p['type']}, {len(p['parts'])} part(s)) ---")
            for part in p["parts"]:
                print(part, f"\n[{tweet_weight(part)} chars]\n")
        return

    client = make_client()
    for p in due:
        publish(client, p, state)


if __name__ == "__main__":
    main()
