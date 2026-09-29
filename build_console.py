"""Generate console.html, a phone-friendly posting page, from content/queue.json."""
import json
from pathlib import Path

from poster import load_queue, tweet_weight

ROOT = Path(__file__).resolve().parent

queue = load_queue()
for p in queue["posts"]:
    p["weights"] = [tweet_weight(t) for t in p["parts"]]
data = json.dumps(queue, ensure_ascii=False).replace("</", "<\\/")
template = (ROOT / "console_template.html").read_text(encoding="utf-8")
(ROOT / "console.html").write_text(template.replace("__QUEUE__", data), encoding="utf-8")
print("wrote console.html")
