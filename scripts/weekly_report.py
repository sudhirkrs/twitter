"""Summarise growth and post performance as Markdown (posted weekly as a GitHub issue).

Reads tracking/growth-log.csv (weekly account numbers) and tracking/post-metrics.csv
(per-post numbers), both filled in from the Control Panel.

Usage:
    python scripts/weekly_report.py > report.md
"""
import csv
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from poster import is_approved, load_queue  # noqa: E402

GROWTH = ROOT / "tracking" / "growth-log.csv"
METRICS = ROOT / "tracking" / "post-metrics.csv"
GOAL = 10_000


def num(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def rate(r):
    views = num(r.get("views")) or 0
    if views <= 0:
        return None
    eng = (num(r.get("likes")) or 0) + 2 * sum(num(r.get(k)) or 0 for k in ("replies", "reposts", "bookmarks"))
    return eng / views


def rows(path):
    return list(csv.DictReader(path.open(encoding="utf-8"))) if path.exists() else []


def latest_per_post(metric_rows):
    """Keep the most recently logged numbers for each post."""
    latest = {}
    for r in metric_rows:
        if r.get("post_id"):
            latest[r["post_id"]] = r
    return list(latest.values())


def build():
    queue = load_queue()
    by_id = {p["id"]: p for p in queue["posts"]}
    out = [f"# Weekly report, {datetime.now(ZoneInfo(queue['timezone'])):%a %d %b %Y}", ""]

    weeks = [r for r in rows(GROWTH) if num(r.get("followers")) is not None]
    out.append("## Followers")
    if weeks:
        last = weeks[-1]
        f = num(last["followers"])
        line = f"**{f:,}** followers (logged {last['week_ending']})"
        if len(weeks) > 1:
            prev = num(weeks[-2]["followers"])
            gain = f - prev
            line += f", **{gain:+,}** since {weeks[-2]['week_ending']}"
            if gain > 0:
                weeks_left = (GOAL - f) / gain
                line += f". At this pace, 10k in about **{weeks_left:.0f} weeks**"
        out += [line + ".", ""]
        out.append("| Week ending | Followers | Impressions | Profile visits |")
        out.append("|---|---:|---:|---:|")
        for r in weeks[-6:]:
            out.append(f"| {r['week_ending']} | {r.get('followers') or ''} | {r.get('impressions') or ''} | {r.get('profile_visits') or ''} |")
    else:
        out.append("_No follower numbers logged yet. Add them in the Control Panel → Log numbers._")
    out.append("")

    for r in rows(METRICS):  # posts read from X that aren't in the schedule (news tweets, your own posts)
        if r.get("post_id") and r["post_id"] not in by_id:
            by_id[r["post_id"]] = {"pillar": "news" if r["post_id"].startswith("n") else "other",
                                   "type": "post", "parts": [r.get("notes") or r["post_id"]]}
    posts = [r for r in latest_per_post(rows(METRICS)) if r["post_id"] in by_id and rate(r) is not None]
    out.append("## Best posts by engagement rate")
    if posts:
        posts.sort(key=rate, reverse=True)
        out += ["| Post | Pillar | Type | Views | Engagement |", "|---|---|---|---:|---:|"]
        for r in posts[:5]:
            p = by_id[r["post_id"]]
            hook = p["parts"][0].splitlines()[0][:60].replace("|", "/")
            out.append(f"| {r['post_id']}: {hook} | {p['pillar']} | {p['type']} | {num(r['views']):,} | {rate(r):.1%} |")
        out.append("")
        for key, label in (("pillar", "pillar"), ("type", "format")):
            groups = defaultdict(list)
            for r in posts:
                groups[by_id[r["post_id"]][key]].append(r)
            out += [f"### By {label}", f"| {label.title()} | Posts | Avg views | Avg engagement |", "|---|---:|---:|---:|"]
            for g, rs in sorted(groups.items(), key=lambda kv: -sum(map(rate, kv[1])) / len(kv[1])):
                avg_v = sum(num(r["views"]) for r in rs) / len(rs)
                avg_e = sum(map(rate, rs)) / len(rs)
                out.append(f"| {g} | {len(rs)} | {avg_v:,.0f} | {avg_e:.1%} |")
            out.append("")
        out.append("_Engagement = (likes + 2 × (replies + reposts + bookmarks)) ÷ views. "
                   "The weekly AI drafter uses your top posts as examples._")
    else:
        out.append("_No post numbers logged yet. Add them in the Control Panel → Log numbers._")
    out.append("")

    start = date.fromisoformat(queue["start_date"])
    today_num = (datetime.now(ZoneInfo(queue["timezone"])).date() - start).days + 1
    last = max(p["day"] for p in queue["posts"])
    drafts = [p for p in queue["posts"] if not is_approved(p) and p["day"] >= today_num]
    out.append("## Content runway")
    out.append(f"Posts are scheduled through **{date.fromordinal(start.toordinal() + last - 1):%a %d %b}** "
               f"({max(last - today_num, 0)} days ahead).")
    if drafts:
        out.append(f"**{len(drafts)} AI drafts are waiting for your approval** in the Control Panel.")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    print(build(), end="")
