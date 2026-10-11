"""Turn fresh news into ready-to-post tweets.

Reads Google News RSS searches for each topic (no key needed), picks the
freshest stories not used before, and writes one tweet per story:
- with an AI model (any OpenAI-compatible API, same LLM_* settings as the
  weekly drafter) when those settings exist;
- otherwise from built-in templates around the headline.
The tweets are saved to content/news.json (with their sources, for your
records), which the Posting Desk build turns into short "Open in X" pages.
The issue shows only the tweets and their Open in X links.

Usage:
    python scripts/news_tweets.py --topic all --count 3 --out issue.md
    python scripts/news_tweets.py --feed-file sample.xml ...   # offline test
"""
import argparse
import base64
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
    "personal-finance": ["RBI repo rate", "income tax India", "SEBI mutual funds", "EPFO PPF interest rate", "home loan EMI India"],
    "stocks": ["Sensex Nifty", "SEBI stock market India", "IPO India"],
    "payments": ["UPI NPCI", "RBI digital payments", "India fintech"],
    "ai": ["AI India banks", "AI fintech India", "AI jobs India"],
}

# Used when no AI key is set: the headline plus a topic line and a question.
# {t} is the headline. Keep them factual: they add no claims of their own.
TEMPLATES = {
    "personal-finance": [
        "{t}\n\nIf you have a loan, an FD or a SIP, this is worth two minutes of your attention.\n\nWill this change any money decision for you? 👇",
        "{t}\n\nSmall changes like this quietly add up in your savings, EMIs and taxes over the years.\n\nWhat's your take? 👇",
    ],
    "stocks": [
        "{t}\n\nMarkets move every day. A long-term plan shouldn't move with every headline.\n\nAre you changing anything, or staying the course? 👇",
        "{t}\n\nWorth knowing, but for a 10-year investor most daily moves are noise.\n\nHow are you reading this one? 👇",
    ],
    "payments": [
        "{t}\n\nThe way India pays keeps changing, and it usually reaches your phone sooner than you think.\n\nGood news or bad news for you? 👇",
        "{t}\n\nPayments news like this ends up in the apps you use every day.\n\nWhat's your take? 👇",
    ],
    "ai": [
        "{t}\n\nAI is changing how money works faster than most people notice.\n\nExcited or worried? 👇",
        "{t}\n\nThis is where AI and your money meet.\n\nWould you trust AI with this? 👇",
    ],
}

SYSTEM_PROMPT = """You write X (Twitter) posts for @Sudhirkrs17, an Indian creator who explains how money
works for salaried Indians aged 22-40. Voice: clear, practical, friendly, no jargon, no hype.

For each news story you are given, write ONE tweet that:
- starts with a hook line, then explains in plain words what happened and why it matters to an
  ordinary Indian's money (savings, loans, payments, investing, jobs).
- uses ONLY facts present in the story's title and summary. Do not add numbers, dates, names or
  claims that are not there. If the summary is thin, keep the tweet general and say "reportedly".
- never gives buy/sell advice or price targets for any stock, fund or coin.
- has no links, no hashtags and no source credits. It must read as your own post, not a headline repost.
- is at most 240 characters (the article link is added after it). Emoji, ₹, •, → count double, so use them sparingly.

Return ONLY JSON: {"tweets": [{"story": <story number>, "text": "<tweet>"}, ...]}"""

URL_RE = re.compile(r"https?://\S+")
LINK_COST = 2 + 23          # blank line + any link (X counts every link as 23)
BODY_MAX = 280 - LINK_COST  # room left for the tweet text


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


def resolve_link(url):
    """Turn a news.google.com redirect into the publisher's article URL, so the
    tweet's preview card shows the real source. Falls back to the original."""
    if "news.google.com" not in url:
        return url
    art_id = urllib.parse.urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
    # Older IDs carry the article URL inside their base64 payload.
    try:
        raw = base64.urlsafe_b64decode(art_id + "=" * (-len(art_id) % 4))
        m = re.search(rb"https?://[\x21-\x7e]+", raw)
        if m and b"AU_yqL" not in raw[:8]:
            return m.group(0).decode()
    except (ValueError, TypeError):
        pass
    # Newer IDs need Google's own lookup (signature + timestamp from the article page).
    try:
        page = fetch(f"https://news.google.com/articles/{art_id}").decode("utf-8", "replace")
        sig = re.search(r'data-n-a-sg="([^"]+)"', page).group(1)
        ts = re.search(r'data-n-a-ts="([^"]+)"', page).group(1)
        inner = json.dumps(["garturlreq", [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None,
                                              None, None, 0, 1], "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
                            art_id, int(ts), sig])
        body = urllib.parse.urlencode({"f.req": json.dumps([[["Fbv4je", inner, None, "generic"]]])}).encode()
        req = urllib.request.Request("https://news.google.com/_/DotsSplashUi/data/batchexecute", data=body,
                                     headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                                              "User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            text = r.read().decode("utf-8", "replace")
        m = re.search(r'garturlres\\",\\"(https?://[^\\"]+)', text)
        if m:
            return m.group(1)
    except Exception as e:  # keep the Google News link if the lookup fails
        print(f"Couldn't resolve {url[:60]}…: {e}", file=sys.stderr)
    return url


def with_link(text, link):
    return f"{text}\n\n{link}"


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


# Headlines that are guides, listicles, price pages or live blogs rather than
# news. Matched case-insensitively against the title.
NOT_NEWS = re.compile("|".join([
    r"\bhow to\b", r"\bhow (do|does|can|much|many)\b", r"\bwhat is\b", r"\bwhat are\b", r"\bexplained\b",
    r"\bexplainer\b", r"\bguide\b", r"\bfaqs?\b", r"\beverything you need to know\b", r"\bstep[- ]by[- ]step\b",
    r"\breview\b", r"\ballotment\b", r"\bgmp\b", r"\bsubscription status\b", r"\bkey dates\b", r"\bdetails\b",
    r"\brules?\s*(&|and)\s*rates?\b", r"\bcalculator\b", r"\btips\b", r"\btop \d+\b",
    r"\b\d+ (ways|things|tips|reasons|mistakes|stocks|funds|best)\b", r"\bbest\b.*\b(to buy|to invest|for \d{4})\b",
    r"\bstocks? to (buy|watch|sell)\b", r"\b(price|rate)s? today\b", r"\btoday'?s (gold|silver|petrol|diesel) (price|rate)\b",
    r"\bshare price (live|today|target)\b", r"\btarget price\b", r"\blive( updates?| blog)?\s*[:|]", r"\bhighlights\b",
    r"\bhoroscope\b", r"\bquiz\b", r"\bsponsored\b", r"\bin pics\b", r"\bwatch:", r"\bvideo\b",
]), re.I)


def is_news(title):
    return not NOT_NEWS.search(title)


def pick(stories, used, count):
    """Freshest unused real-news stories, spread across topics."""
    seen_titles = set()
    fresh = []
    skipped = 0
    for s in sorted(stories, key=lambda s: s["published"], reverse=True):
        key = norm(s["title"])
        if s["url"] in used["urls"] or key in used["titles"] or key in seen_titles:
            continue
        if not is_news(s["title"]):
            skipped += 1
            continue
        seen_titles.add(key)
        fresh.append(s)
    chosen, by_topic = [], {}
    for s in fresh:  # round-robin over topics
        by_topic.setdefault(s["topic"], []).append(s)
    if skipped:
        print(f"Skipped {skipped} guide/listicle headline(s).", file=sys.stderr)
    while len(chosen) < count and any(by_topic.values()):
        for t in list(by_topic):
            if by_topic[t] and len(chosen) < count:
                chosen.append(by_topic[t].pop(0))
    return chosen


def call_llm(messages):
    body = json.dumps({"model": os.environ["LLM_MODEL"].strip().removeprefix("models/"), "messages": messages, "temperature": 0.7}).encode()
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
            elif x_weight(texts[i]) > BODY_MAX:
                problems.append(f"story {i}: {x_weight(texts[i])} characters, max {BODY_MAX}")
            elif URL_RE.search(texts[i]):
                problems.append(f"story {i}: remove the link")
        if not problems:
            return [texts[i + 1] for i in range(len(stories))]
        print(f"Attempt {attempt}: {problems}", file=sys.stderr)
        messages += [{"role": "assistant", "content": reply},
                     {"role": "user", "content": "Fix these and return the full JSON again:\n- " + "\n- ".join(problems)}]
    sys.exit("The model did not return valid tweets after several attempts.")


def template_tweet(story, k):
    title = story["title"].strip()
    if title[-1:] not in ".?!":
        title += "."
    options = TEMPLATES[story["topic"]]
    text = options[k % len(options)].format(t=title)
    while x_weight(text) > BODY_MAX and len(title) > 40:  # very long headline: shorten it
        title = title[: len(title) - 10].rsplit(" ", 1)[0] + "…"
        text = options[k % len(options)].format(t=title)
    return text


def load_news():
    if NEWS_FILE.exists():
        return json.loads(NEWS_FILE.read_text(encoding="utf-8"))
    return {"items": []}


def issue_body(items, have_llm):
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    out = [f"## News tweets, {now:%a %d %b %Y, %H:%M} IST", "",
           "Tap **Open in X** under a tweet, then Post. The links start working about 2 minutes after this issue appears.", ""]
    if have_llm:
        out += ["_Written by AI from today's news: read each one before posting, AI can get details wrong._", ""]
    else:
        out += ["_Written from templates around the headline. Add the LLM_* secrets for AI-written tweets._", ""]
    for i, it in enumerate(items, 1):
        out += [f"### Tweet {i} · {it['topic']} ({x_weight(it['text'])} chars)", "```text", it["text"], "```",
                f"**[➜ Open in X]({DESK_URL}p/{it['id']}.html)**", ""]
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
    texts = write_tweets(stories) if have_llm else [template_tweet(s, k) for k, s in enumerate(stories)]
    links = [resolve_link(s["url"]) for s in stories]
    stamp = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y%m%d%H%M")
    items = []
    for k, (s, text, link) in enumerate(zip(stories, texts, links), 1):
        items.append({"id": f"n{stamp}-{k}", "created": datetime.now(timezone.utc).isoformat(timespec="minutes"),
                      **s, "link": link, "text": with_link(text, link), "writer": "ai" if have_llm else "template"})
    news["items"] = (news["items"] + items)[-KEEP_ITEMS:]
    NEWS_FILE.write_text(json.dumps(news, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(args.out).write_text(issue_body(items, have_llm), encoding="utf-8")
    print(f"Wrote {len(items)} news item(s).")


if __name__ == "__main__":
    main()
