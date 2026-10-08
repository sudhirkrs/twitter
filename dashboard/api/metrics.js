// GET: both tracking CSVs. POST {kind: "post"|"week", row}: append one row.
const { send, readJson, getFile, putFile, handler } = require("./_lib");

const FILES = {
  post: { path: "tracking/post-metrics.csv", cols: ["date_logged", "post_id", "views", "likes", "replies", "reposts", "bookmarks", "follows", "notes"] },
  week: { path: "tracking/growth-log.csv", cols: ["week_ending", "followers", "new_followers", "impressions", "profile_visits", "posts", "replies_made", "top_post", "notes"] },
};

function cell(v) {
  const s = v === undefined || v === null ? "" : String(v).replace(/[\r\n]+/g, " ");
  return /[",]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}

async function readText(path, cols) {
  try {
    return await getFile(path);
  } catch (e) {
    if (e.status === 404) return { sha: undefined, text: cols.join(",") + "\n" };
    throw e;
  }
}

async function appendLines(f, lines, message) {
  for (let attempt = 0; attempt < 2; attempt++) {
    const cur = await readText(f.path, f.cols);
    try {
      return await putFile(f.path, cur.text.replace(/\n*$/, "\n") + lines.join("\n") + "\n", cur.sha, message);
    } catch (e) {
      if (e.status !== 409 || attempt) throw e; // someone else saved first: re-read and retry once
    }
  }
}

module.exports = handler(async (req, res) => {
  if (req.method === "GET") {
    const [post, week] = await Promise.all([
      readText(FILES.post.path, FILES.post.cols),
      readText(FILES.week.path, FILES.week.cols),
    ]);
    return send(res, 200, { posts: post.text, growth: week.text });
  }
  if (req.method === "POST") {
    const body = await readJson(req);
    if (body.kind === "batch") {
      const rows = Array.isArray(body.rows) ? body.rows.slice(0, 200) : [];
      if (rows.length) await appendLines(FILES.post, rows.map((r) => FILES.post.cols.map((c) => cell(r[c])).join(",")), "Import post numbers read from X");
      if (body.week) await appendLines(FILES.week, [FILES.week.cols.map((c) => cell(body.week[c])).join(",")], "Log follower count read from X");
      return send(res, 200, { ok: true, saved: rows.length });
    }
    const { kind, row } = body;
    const f = FILES[kind];
    if (!f || !row) return send(res, 400, { error: "kind must be post or week, with a row" });
    const line = f.cols.map((c) => cell(row[c])).join(",");
    for (let attempt = 0; attempt < 2; attempt++) {
      const cur = await readText(f.path, f.cols);
      const text = cur.text.replace(/\n*$/, "\n") + line + "\n";
      try {
        await putFile(f.path, text, cur.sha, `Log ${kind === "post" ? "post" : "weekly"} numbers from the Control Panel`);
        return send(res, 200, { ok: true });
      } catch (e) {
        if (e.status !== 409 || attempt) throw e; // someone else saved first: re-read and retry once
      }
    }
  }
  send(res, 405, { error: "Use GET or POST" });
});
