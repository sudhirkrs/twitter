"""Generate the Posting Desk page from content/queue.json.

Writes:
  console.html      the page body, published as a Claude artifact
  site/index.html   the same page as a standalone site, deployed to GitHub Pages
"""
import json
from pathlib import Path

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
print("wrote console.html and site/index.html")
