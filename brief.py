"""Build the daily posting brief (Markdown) for one date from content/queue.json.

Each single tweet gets a one-tap link that opens the X composer pre-filled.
Threads: the link fills the first part; reply to it with the remaining parts.

Usage:
    python brief.py                 # today's brief (IST)
    python brief.py --date 2026-10-01
"""
import argparse
from datetime import date, datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo

from poster import load_queue, scheduled_at, tweet_weight

INTENT = "https://x.com/intent/post?text="


def intent_link(text):
    return INTENT + quote(text, safe="")


def build(queue, day):
    posts = sorted(
        (p for p in queue["posts"] if scheduled_at(queue, p).date() == day),
        key=lambda p: scheduled_at(queue, p),
    )
    start = date.fromisoformat(queue["start_date"])
    lines = [f"## Day {(day - start).days + 1}: {day:%A, %d %B %Y}", ""]
    if day < start:
        return f"Posting starts on {start:%A, %d %B %Y}. Use today to set up your profile (see STRATEGY.md §1).\n"
    if not posts:
        lines.append("_No posts scheduled today. Add more to `content/queue.json`._")
    for p in posts:
        when = scheduled_at(queue, p)
        lines += [f"### {when:%H:%M} IST: {p['type']} ({p['pillar']})", ""]
        if p["type"] == "poll":
            opts = ", ".join(p["poll"]["options"])
            lines += [f"Poll (create it in the X app). Options: **{opts}**. Duration: 1 day.", ""]
        for i, part in enumerate(p["parts"], 1):
            if len(p["parts"]) > 1:
                label = "Post this first" if i == 1 else f"Then reply to part {i - 1} with"
                lines.append(f"**{i}/{len(p['parts'])}**: {label} ({tweet_weight(part)} chars)")
            lines += ["```text", part, "```"]
            if i == 1 and p["type"] != "poll":
                lines.append(f"[➜ Open in X, pre-filled]({intent_link(part)})")
            lines.append("")
    lines += [
        "---",
        "### Today's reply routine (45 min)",
        "- [ ] Morning: 5–10 value replies on fresh posts from bigger accounts",
        "- [ ] Reply to every comment on your posts in their first hour",
        "- [ ] Evening: 5–10 more value replies, plus 1 quote-post with your take",
        "- [ ] Engage with 5 accounts at your level (500–5k followers)",
    ]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYY-MM-DD (default: today in the queue's timezone)")
    args = ap.parse_args()
    queue = load_queue()
    day = (date.fromisoformat(args.date) if args.date
           else datetime.now(ZoneInfo(queue["timezone"])).date())
    print(build(queue, day), end="")


if __name__ == "__main__":
    main()
