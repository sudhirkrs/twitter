// Shared helpers for the Control Panel API. Files starting with "_" are not routes.
const crypto = require("crypto");

const REPO = process.env.GITHUB_REPO || "sudhirkrs/twitter";
const BRANCH = process.env.GITHUB_BRANCH || "main";

function send(res, status, body) {
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");
  res.end(JSON.stringify(body));
}

// Every request must carry the ADMIN_PASSWORD set in Vercel, in the x-admin-key header.
function authorised(req) {
  const want = process.env.ADMIN_PASSWORD || "";
  const got = String(req.headers["x-admin-key"] || "");
  if (!want) return false;
  const a = crypto.createHash("sha256").update(want).digest();
  const b = crypto.createHash("sha256").update(got).digest();
  return crypto.timingSafeEqual(a, b);
}

async function readJson(req) {
  if (req.body !== undefined && req.body !== null) {
    return typeof req.body === "string" ? JSON.parse(req.body) : req.body;
  }
  const chunks = [];
  for await (const c of req) chunks.push(c);
  return chunks.length ? JSON.parse(Buffer.concat(chunks).toString("utf8")) : {};
}

async function github(path, options = {}) {
  if (!process.env.GITHUB_TOKEN) throw Object.assign(new Error("GITHUB_TOKEN is not set in Vercel"), { status: 500 });
  const r = await fetch("https://api.github.com" + path, {
    ...options,
    headers: {
      Authorization: "Bearer " + process.env.GITHUB_TOKEN,
      Accept: "application/vnd.github+json",
      "User-Agent": "twitter-control-panel",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
    },
  });
  const text = await r.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (!r.ok) {
    const msg = (data && data.message) || text || r.statusText;
    throw Object.assign(new Error("GitHub " + r.status + ": " + msg), { status: r.status });
  }
  return data;
}

async function getFile(path) {
  const d = await github(`/repos/${REPO}/contents/${path}?ref=${encodeURIComponent(BRANCH)}`);
  return { sha: d.sha, text: Buffer.from(d.content, "base64").toString("utf8") };
}

async function putFile(path, text, sha, message) {
  const d = await github(`/repos/${REPO}/contents/${path}`, {
    method: "PUT",
    body: JSON.stringify({ message, content: Buffer.from(text, "utf8").toString("base64"), sha, branch: BRANCH }),
  });
  return d.content.sha;
}

// X counts these code point ranges as 1 character and everything else
// (emoji, ₹, •, →) as 2. Mirrors poster.py.
const LIGHT = [[0, 4351], [8192, 8205], [8208, 8223], [8242, 8247]];
function tweetWeight(text) {
  let w = 0;
  for (const ch of String(text).normalize("NFC")) {
    const cp = ch.codePointAt(0);
    w += LIGHT.some(([lo, hi]) => cp >= lo && cp <= hi) ? 1 : 2;
  }
  return w;
}

// Mirrors poster.check(): returns a list of problems.
function checkQueue(q) {
  const errors = [];
  if (!q || !Array.isArray(q.posts) || !q.slots || !q.start_date || !q.timezone) return ["queue is missing posts, slots, start_date or timezone"];
  const seen = new Set();
  for (const p of q.posts) {
    const id = p.id;
    if (seen.has(id)) errors.push(`${id}: duplicate id`);
    seen.add(id);
    if (!Number.isInteger(p.day) || p.day < 1) errors.push(`${id}: day must be a positive whole number`);
    if (!(p.slot in q.slots)) errors.push(`${id}: unknown slot ${p.slot}`);
    if (!["tweet", "thread", "poll"].includes(p.type)) errors.push(`${id}: type must be tweet, thread or poll`);
    if (!["approved", "draft", undefined].includes(p.status)) errors.push(`${id}: status must be approved or draft`);
    if (!Array.isArray(p.parts) || !p.parts.length || p.parts.some((t) => !String(t).trim())) errors.push(`${id}: every part needs text`);
    (p.parts || []).forEach((t, i) => {
      const w = tweetWeight(t);
      if (w > 280) errors.push(`${id} part ${i + 1}: ${w}/280 characters`);
    });
    if (p.type === "poll") {
      const opts = (p.poll && p.poll.options) || [];
      if (opts.length < 2 || opts.length > 4 || opts.some((o) => !o || o.length > 25)) errors.push(`${id}: poll needs 2-4 options of up to 25 characters`);
      if ((p.parts || []).length !== 1) errors.push(`${id}: a poll is a single tweet`);
    }
  }
  return errors;
}

function handler(fn) {
  return async (req, res) => {
    if (!authorised(req)) return send(res, 401, { error: "Wrong or missing password." });
    try {
      await fn(req, res);
    } catch (e) {
      send(res, e.status === 409 || e.status === 422 ? 409 : e.status || 500, { error: e.message });
    }
  };
}

module.exports = { REPO, BRANCH, send, readJson, github, getFile, putFile, tweetWeight, checkQueue, handler };
