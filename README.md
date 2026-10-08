# @Sudhirkrs17 growth engine

A self-running system to grow [@Sudhirkrs17](https://x.com/Sudhirkrs17) to 10,000+ followers, built on **GitHub and Vercel only**. No paid X API is needed: you post with one tap, and everything else is prepared, drafted and measured for you.

## How it works

| Piece | Where | What it does |
|---|---|---|
| **Daily brief** | GitHub Issues ([`daily-brief.yml`](.github/workflows/daily-brief.yml)) | Every evening, opens an issue with the **next day's** posts and an **➜ Open in X** link under each one |
| **Posting Desk** | GitHub Pages: https://sudhirkrs.github.io/twitter/ | Phone page for any day: Open in X, Open X app, Copy for thread parts |
| **Control Panel** | Vercel ([`dashboard/`](dashboard/)) | Edit, approve, add and delete posts; log your numbers; see Insights; start any job |
| **Weekly AI drafts** | GitHub Actions ([`draft-week.yml`](.github/workflows/draft-week.yml)) | Every Sunday, drafts the next 7 days with an AI model you choose, when fewer than 14 days are queued. Drafts wait for your approval. |
| **Weekly report** | GitHub Issues ([`weekly-report.yml`](.github/workflows/weekly-report.yml)) | Every Sunday evening: follower trend, best posts, best topics and formats, content runway |
| **Content** | [`content/queue.json`](content/queue.json) | All posts. `"status": "draft"` posts get no Open in X link until approved. |
| **Numbers** | [`tracking/`](tracking/) | `growth-log.csv` (weekly account numbers) and `post-metrics.csv` (per post), written by the Control Panel |
| **Strategy** | [`STRATEGY.md`](STRATEGY.md) | Positioning, profile, content pillars, the daily reply routine, milestones |

## Your routine

**Daily (about 5 minutes of posting, plus replies)**
1. **Evening before:** a GitHub notification arrives, e.g. "Posts for Fri 09 Oct 2026". (It's prepared a day ahead because GitHub often starts scheduled jobs hours late.)
2. **08:30:** in the issue, tap **➜ Open in X** under the morning post → **Post**. For threads, post part 1, then reply with each next part, long-pressing a box to copy it.
3. **19:30:** same for the evening post. Polls: create them in the X app with the options shown.
4. Spend 45 minutes replying to bigger accounts (`STRATEGY.md` §3). That's where the growth comes from.

**Sunday (about 20 minutes)**
1. Control Panel → **Log numbers**: your follower count, and the numbers under each of the week's posts.
2. Read the **Weekly report** issue, or the Control Panel's **Insights** tab.
3. Control Panel → **Posts**: edit the new AI drafts, then tap **Approve this day**. Check every number and claim; the AI can be wrong.

## One-time setup

GitHub Pages and the daily brief are already running. Two things remain.

### 1. Control Panel on Vercel (about 10 minutes)

1. **Create a GitHub token** the panel will use to save changes: github.com → Settings → Developer settings → **Fine-grained tokens** → Generate new token.
   - Repository access: **Only select repositories** → `sudhirkrs/twitter`
   - Permissions: **Contents: Read and write**, **Actions: Read and write** (Metadata: Read is added automatically)
   - Set an expiry you're comfortable with, and put a reminder in your calendar to renew it.
2. **Import the repo on Vercel:** vercel.com → **Add New… → Project** → import `sudhirkrs/twitter`.
   - **Root Directory:** `dashboard`
   - **Framework Preset:** Other (no build command needed)
   - **Environment Variables:**
     - `ADMIN_PASSWORD`: a long password only you know. It's the panel's login.
     - `GITHUB_TOKEN`: the token from step 1
   - Click **Deploy**. Vercel gives you an address like `https://twitter-xxxx.vercel.app`.
3. **Tell GitHub where the panel is:** repo **Settings → Secrets and variables → Actions → Variables** → add `CONTROL_PANEL_URL` = your Vercel address. The "drafts ready" notification links to it.

Vercel redeploys only when something in `dashboard/` changes. Saving posts doesn't trigger a Vercel build.

### 2. Weekly AI drafts (about 5 minutes)

The drafter works with any **OpenAI-compatible** AI service, so you choose the provider. For example, Google's Gemini API has a free tier: create a key at Google AI Studio, then use its OpenAI-compatible address. Check your provider's current free limits and model names; they change often.

Add three **repository secrets** (Settings → Secrets and variables → Actions → Secrets):

| Secret | Example (Google Gemini) |
|---|---|
| `LLM_API_KEY` | your API key |
| `LLM_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta/openai` |
| `LLM_MODEL` | a model name listed in your provider's docs |

Test it: Control Panel → **Automation** → tick "Draft 7 more days" → **Draft now**. After a minute or two, a "New AI drafts ready for review" issue appears and the drafts show under **Posts**.

Without these secrets, everything else keeps working; only the automatic weekly drafts are skipped, and you add posts yourself in the Control Panel.

## Files

| File | Purpose |
|---|---|
| `poster.py` | Shared helpers. `python poster.py --check` validates every post against X's 280-character weighting (emoji, ₹, • and → count as 2). |
| `brief.py` | Builds a daily brief: `python brief.py --date 2026-10-09` |
| `build_console.py` | Builds the Posting Desk and the short Open-in-X pages into `site/` |
| `scripts/draft_week.py` | The AI drafter. `--dry-run` prints the prompt; `--force` drafts regardless of runway. |
| `scripts/weekly_report.py` | The weekly report |
| `dashboard/` | The Vercel Control Panel: `index.html` plus API functions in `api/` (no dependencies) |
