"""Turn fresh news into tweet drafts.

Reads Google News RSS searches for each topic (no key needed), picks the
freshest stories not used before, and asks an AI model (any OpenAI-compatible
API, same LLM_* settings as the weekly drafter) to write one tweet per story.
The tweets are saved to content/news.json, which the Posting Desk build turns
into short "Open in X" pages, and a Markdown issue body is written for review.

Without the LLM_* settings it still lists the stories, so you can write the
tweets yourself.

Usage:
    python scripts/news_tweets.py --topic all --count 3 --out issue.md
    python scripts/news_tweets.py --feed-file sample.xml ...   # offline test
"""
import argparse
import email.utils
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from poster import tweet_weight  # noqa: E402

NEWS_FILE = ROOT / "content" / "news.json"
DESK_URL = "https://sudhirkrs.github.io/twitter/"
KEEP_ITEMS = 300
ATTEMPTS = 3

# Google News searches per topic. Edit freely; "when:2d" keeps results fresh.
TOPICS = {
    "personal-finance": ["personal finance India", "mutual funds SEBI", "income tax India", "RBI repo rate"],
    "stocks": ["Sensex Nifty market", "Indian stock market"],
    "payments": ["UPI NPCI", "RBI payments", "fintech India"],
    "ai": ["AI banking India", "artificial intelligence finance"],
}

SYSTEM_PROMPT = """You write X (Twitter) posts for @Sudhirkrs17, an Indian creator who explains how money
works for salaried Indians aged 22-40. Voice: clear, practical, friendly, no jargon, no hype.

For each news story you are given, write ONE tweet that:
- starts with a hook line, then explains in plain words what happened and why it matters to an
  ordinary Indian's money (savings, loans, payments, investing, jobs).
- uses ONLY facts present in the story's title and summary. Do not add numbers, dates, names or
  claims that are not there. If the summary is thin, keep the tweet general and say "reportedly".
- never gives buy/sell advice or price targets for any stock, fund or coin.
- has no links and no hashtags (the source link is added separately as a reply).
- is at most 260 characters. Emoji, ₹, •, → count double, so use them sparingly.

Return ONLY JSON: {"tweets": [{"story": <story number>, "text": "<tweet>"}, ...]}"""

URL_RE = re.compile(r"https?://\S+")


def x_weight(text):
    """X counts every link as 23 characters."""
    return tweet_weight(URL_RE.sub("x" * 23, text))


def feed_url(query):
    q = urllib.parse.quote(f"{query} when:2d")
    return f"https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (news-tweets; +https://github.com/sudhirkrs/twitter)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def strip_html(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def parse_feed(xml_bytes, topic):
    items = []
    for it in ET.fromstring(xml_bytes).iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        src = it.find("source")
        source = (src.text or "").strip() if src is not None else ""
        if source and title.endswith(" - " + source):
            title = title[: -len(" - " + source)]
        try:
            published = email.utils.parsedate_to_datetime(it.findtext("pubDate"))
        except (TypeError, ValueError):
            published = datetime.now(timezone.utc)
        if title and link:
            items.append({"topic": topic, "title": title, "url": link, "source": source,
                          "published": published.astimezone(timezone.utc).isoformat(timespec="minutes"),
                          "summary": strip_html(it.findtext("description"))[:500]})
    return items


def norm(title):
    return re.sub(r"[^a-z0-9 ]", "", title.lower())[:70]


def gather(topics, feed_file=None):
    stories = []
    for topic in topics:
        for query in TOPICS[topic]:
            try:
                data = Path(feed_file).read_bytes() if feed_file else fetch(feed_url(query))
                stories += parse_feed(data, topic)
            except Exception as e:  # one bad feed shouldn't stop the run
                print(f"Skipping feed {query!r}: {e}", file=sys.stderr)
    return stories


def pick(stories, used, count):
    """Freshest unused stories, spread across topics."""
    seen_titles = set()
    fresh = []
    for s in sorted(stories, key=lambda s: s["published"], reverse=True):
        key = norm(s["title"])
        if s["url"] in used["urls"] or key in used["titles"] or key in seen_titles:
            continue
        seen_titles.add(key)
        fresh.append(s)
    chosen, by_topic = [], {}
    for s in fresh:  # round-robin over topics
        by_topic.setdefault(s["topic"], []).append(s)
    while len(chosen) < count and any(by_topic.values()):
        for t in list(by_topic):
            if by_topic[t] and len(chosen) < count:
                chosen.append(by_topic[t].pop(0))
    return chosen


def call_llm(messages):
    body = json.dumps({"model": os.environ["LLM_MODEL"], "messages": messages, "temperature": 0.7}).encode()
    req = urllib.request.Request(
        os.environ["LLM_BASE_URL"].rstrip("/") + "/chat/completions", data=body, method="POST",
        headers={"Authorization": "Bearer " + os.environ["LLM_API_KEY"], "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)["choices"][0]["message"]["content"]


def write_tweets(stories):
    listing = [{"story": i + 1, "topic": s["topic"], "title": s["title"], "source": s["source"],
                "published": s["published"], "summary": s["summary"]} for i, s in enumerate(stories)]
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(listing, ensure_ascii=False, indent=1)}]
    for attempt in range(1, ATTEMPTS + 1):
        reply = call_llm(messages)
        problems, texts = [], {}
        try:
            for t in json.loads(re.search(r"\{.*\}", reply, re.S).group(0))["tweets"]:
                texts[int(t["story"])] = t["text"].strip()
        except Exception as e:
            problems.append(f"could not read the JSON: {e}")
        for i in range(1, len(stories) + 1):
            if i not in texts:
                problems.append(f"story {i}: missing tweet")
            elif x_weight(texts[i]) > 280:
                problems.append(f"story {i}: {x_weight(texts[i])} characters, max 280")
            elif URL_RE.search(texts[i]):
                problems.append(f"story {i}: remove the link")
        if not problems:
            return [texts[i + 1] for i in range(len(stories))]
        print(f"Attempt {attempt}: {problems}", file=sys.stderr)
        messages += [{"role": "assistant", "content": reply},
                     {"role": "user", "content": "Fix these and return the full JSON again:\n- " + "\n- ".join(problems)}]
    sys.exit("The model did not return valid tweets after several attempts.")


def load_news():
    if NEWS_FILE.exists():
        return json.loads(NEWS_FILE.read_text(encoding="utf-8"))
    return {"items": []}


def issue_body(items, have_llm):
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    out = [f"## News tweets, {now:%a %d %b %Y, %H:%M} IST", ""]
    if have_llm:
        out += ["Check each tweet against its source before posting: AI can get details wrong. "
                "Tap **Open in X**, post, then **reply to your own tweet** with the source line (links in the "
                "main tweet reduce reach). Open in X links start working about 2 minutes after this issue appears.", ""]
    else:
        out += ["_No AI key is set (LLM_* secrets), so these are headlines only. Write your own take on one._", ""]
    for i, it in enumerate(items, 1):
        when = datetime.fromisoformat(it["published"]).astimezone(ZoneInfo("Asia/Kolkata"))
        out += [f"### {i}. {it['title']}", f"_{it['source'] or 'source'} · {when:%d %b, %H:%M} IST · {it['topic']}_", ""]
        if it.get("text"):
            out += ["**Tweet** (" + str(x_weight(it["text"])) + " chars)", "```text", it["text"], "```",
                    f"**[➜ Open in X]({DESK_URL}p/{it['id']}.html)**", "",
                    "**Reply with**", "```text", f"Source: {it['url']}", "```", ""]
        else:
            out += ["Source:", "```text", it["url"], "```", ""]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default="all", choices=["all", *TOPICS])
    ap.add_argument("--count", type=int, default=3)
    ap.add_argument("--out", default="issue.md")
    ap.add_argument("--feed-file", help="read every feed from this local RSS file (testing)")
    args = ap.parse_args()

    topics = list(TOPICS) if args.topic == "all" else [args.topic]
    news = load_news()
    used = {"urls": {i["url"] for i in news["items"]}, "titles": {norm(i["title"]) for i in news["items"]}}
    stories = pick(gather(topics, args.feed_file), used, max(1, min(args.count, 8)))
    if not stories:
        Path(args.out).write_text("No new stories found for these topics in the last 2 days. Try again later or pick another topic.\n", encoding="utf-8")
        print("No new stories.")
        return

    have_llm = all(os.environ.get(k) for k in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"))
    texts = write_tweets(stories) if have_llm else [None] * len(stories)
    stamp = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y%m%d%H%M")
    items = []
    for k, (s, text) in enumerate(zip(stories, texts), 1):
        item = {"id": f"n{stamp}-{k}", "created": datetime.now(timezone.utc).isoformat(timespec="minutes"), **s}
        if text:
            item["text"] = text
        items.append(item)
    news["items"] = (news["items"] + items)[-KEEP_ITEMS:]
    NEWS_FILE.write_text(json.dumps(news, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(args.out).write_text(issue_body(items, have_llm), encoding="utf-8")
    print(f"Wrote {len(items)} news item(s).")


if __name__ == "__main__":
    main()
