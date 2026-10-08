// GET: the content queue. PUT {sha, queue}: validate and commit it.
const { send, readJson, getFile, putFile, checkQueue, handler } = require("./_lib");

const PATH = "content/queue.json";

module.exports = handler(async (req, res) => {
  if (req.method === "GET") {
    const f = await getFile(PATH);
    return send(res, 200, { sha: f.sha, queue: JSON.parse(f.text) });
  }
  if (req.method === "PUT") {
    const { sha, queue, message } = await readJson(req);
    const errors = checkQueue(queue);
    if (errors.length) return send(res, 400, { error: "Fix these before saving", errors });
    queue.posts.sort((a, b) => a.day - b.day || a.slot.localeCompare(b.slot));
    const newSha = await putFile(PATH, JSON.stringify(queue, null, 2) + "\n", sha, message || "Update posts from the Control Panel");
    return send(res, 200, { sha: newSha });
  }
  send(res, 405, { error: "Use GET or PUT" });
});
