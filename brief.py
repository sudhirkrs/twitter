"""Build the daily posting brief (Markdown) for one date from content/queue.json.

Each post gets an "Open in X" link that opens the X composer pre-filled,
so posting works straight from the issue. GitHub strips links longer than
~140 characters, so the link goes to a short page on GitHub Pages
(site/p/<id>.html) that forwards to X. The post text is shown for copying.

Usage:
    python brief.py                 # today's brief (IST)
    python brief.py --date 2026-10-01
"""
import argparse
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from poster import is_approved, load_queue, scheduled_at, tweet_weight

DESK_URL = "https://sudhirkrs.github.io/twitter/"


def open_link(post):
    return f"{DESK_URL}p/{post['id']}.html"


def build(queue, day):
    posts = sorted(
        (p for p in queue["posts"] if scheduled_at(queue, p).date() == day),
        key=lambda p: scheduled_at(queue, p),
    )
    start = date.fromisoformat(queue["start_date"])
    lines = [
        f"## Day {(day - start).days + 1}: {day:%A, %d %B %Y}", "",
        "Tap **Open in X** under a post: X opens with the text filled in, then tap Post.", "",
        f"_Backup: if a link doesn't open X, long-press it and choose \"Open in browser\", use the "
        f"[Posting Desk]({DESK_URL}#d{(day - start).days + 1}), or copy the text from the box._", "",
    ]
    if day < start:
        return f"Posting starts on {start:%A, %d %B %Y}. Use today to set up your profile (see STRATEGY.md §1).\n"
    if not posts:
        lines.append("_No posts scheduled today. Add more in the Control Panel or run the \"Draft next week\" workflow._")
    last_day = start + timedelta(days=max(p["day"] for p in queue["posts"]) - 1)
    if (last_day - day).days < 5:
        lines += [f"> ⚠️ **Content runs out on {last_day:%a %d %b}.** Draft and approve more posts in the Control Panel.", ""]
    if any(not is_approved(p) for p in posts):
        lines += ["> ⚠️ **Some posts below are unapproved AI drafts.** Review and approve them in the Control Panel; "
                  "drafts have no Open in X link until approved.", ""]
    for p in posts:
        when = scheduled_at(queue, p)
        flag = "" if is_approved(p) else " · ⚠️ DRAFT, not approved"
        lines += [f"### {when:%H:%M} IST: {p['type']} ({p['pillar']}){flag}", ""]
        if p["type"] == "poll":
            opts = ", ".join(p["poll"]["options"])
            lines += [f"Poll (create it in the X app). Options: **{opts}**. Duration: 1 day.", ""]
        for i, part in enumerate(p["parts"], 1):
            if len(p["parts"]) > 1:
                label = "Post this first" if i == 1 else f"Then reply to part {i - 1} with"
                lines.append(f"**{i}/{len(p['parts'])}**: {label} ({tweet_weight(part)} chars)")
            lines += ["```text", part, "```"]
            if i == 1 and p["type"] != "poll" and is_approved(p):
                lines.append(f"**[➜ Open in X]({open_link(p)})**")
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
