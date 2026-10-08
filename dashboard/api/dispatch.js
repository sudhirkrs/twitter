// POST {workflow, inputs}: start one of the repo's GitHub Actions workflows.
const { REPO, BRANCH, send, readJson, github, handler } = require("./_lib");

const ALLOWED = {
  "draft-week.yml": ["force"],
  "daily-brief.yml": [],
  "weekly-report.yml": [],
  "pages.yml": [],
};

module.exports = handler(async (req, res) => {
  if (req.method !== "POST") return send(res, 405, { error: "Use POST" });
  const { workflow, inputs = {} } = await readJson(req);
  if (!(workflow in ALLOWED)) return send(res, 400, { error: "Unknown workflow" });
  const clean = {};
  for (const k of ALLOWED[workflow]) if (k in inputs) clean[k] = String(inputs[k]);
  await github(`/repos/${REPO}/actions/workflows/${workflow}/dispatches`, {
    method: "POST",
    body: JSON.stringify({ ref: BRANCH, inputs: clean }),
  });
  send(res, 200, { ok: true, actions: `https://github.com/${REPO}/actions/workflows/${workflow}` });
});
