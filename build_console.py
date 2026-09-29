"""Generate the Posting Desk page from content/queue.json.

Writes:
  console.html          the page body, published as a Claude artifact
  site/index.html       the same page as a standalone site, deployed to GitHub Pages
  site/p/<post id>.html short links that forward to X with the post pre-filled.
                        GitHub strips links longer than ~140 characters from issues,
                        so the daily brief links to these instead of X directly.
"""
import html
import json
from pathlib import Path
from urllib.parse import quote

from poster import load_queue, tweet_weight

ROOT = Path(__file__).resolve().parent

queue = load_queue()
for p in queue["posts"]:
    p["weights"] = [tweet_weight(t) for t in p["parts"]]
data = json.dumps(queue, ensure_ascii=False).replace("</", "<\\/")
page = (ROOT / "console_template.html").read_text(encoding="utf-8").replace("__QUEUE__", data)
(ROOT / "console.html").write_text(page, encoding="utf-8")

site = ROOT / "site"
site.mkdir(exist_ok=True)
(site / "index.html").write_text(
    '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
    '<meta name="robots" content="noindex">\n'
    "<style>body{margin:0}[hidden]{display:none!important}</style>\n</head>\n<body>\n"
    + page + "\n</body>\n</html>\n",
    encoding="utf-8",
)
REDIRECT = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<meta http-equiv="refresh" content="0; url={url}">
<title>Opening X…</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;margin:0;padding:24px 16px;max-width:560px}}
a{{color:#0E7A5C;font-weight:600}}pre{{white-space:pre-wrap;background:#EEF3F1;padding:12px;border-radius:8px}}</style>
</head>
<body>
<p>Opening X with your post filled in…</p>
<p>If nothing happens, <a href="{url}">tap here to open X</a>, or copy the text below.</p>
<pre>{text}</pre>
<script>location.replace({url_js});</script>
</body>
</html>
"""

short = site / "p"
short.mkdir(exist_ok=True)
for p in queue["posts"]:
    if p["type"] == "poll":
        continue
    url = "https://twitter.com/intent/tweet?text=" + quote(p["parts"][0], safe="")
    (short / f"{p['id']}.html").write_text(
        REDIRECT.format(url=html.escape(url), url_js=json.dumps(url), text=html.escape(p["parts"][0])),
        encoding="utf-8",
    )
print("wrote console.html, site/index.html and site/p/*.html")
