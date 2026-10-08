# @Sudhirkrs17 growth engine

A self-running system to grow [@Sudhirkrs17](https://x.com/Sudhirkrs17) to 10,000+ followers, built on **GitHub and Vercel only**. No paid X API is needed: you post with one tap, and everything else is prepared, drafted and measured for you.

## How it works

| Piece | Where | What it does |
|---|---|---|
| **Daily brief** | GitHub Issues ([`daily-brief.yml`](.github/workflows/daily-brief.yml)) | Every evening, opens an issue with the **next day's** posts and an **➜ Open in X** link under each one |
| **Posting Desk** | GitHub Pages: https://sudhirkrs.github.io/twitter/ | Phone page for any day: Open in X, Open X app, Copy for thread parts |
| **News tweets** | GitHub Actions ([`news-tweets.yml`](.github/workflows/news-tweets.yml)), run on demand | Reads the latest Indian news on personal finance, stocks, payments or AI and turns each story into a ready-to-post tweet (AI-written with an AI key, template-based without). The issue has just the tweets, each with an **Open in X** link. |
| **Control Panel** | Vercel ([`dashboard/`](dashboard/)) | Edit, approve, add and delete posts; log your numbers; see Insights; start any job, including News tweets |
| **X numbers bookmark** | Your own browser ([`dashboard/x-reader.js`](dashboard/x-reader.js)) | On your X profile, signed in, it reads the views, likes, replies, reposts and bookmarks under your posts plus your follower count, and sends them to the Control Panel to review and save. It only reads the screen; no password leaves your browser. |
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

**Whenever there's news worth covering**
1. GitHub → **Actions → News tweets → Run workflow** (or Control Panel → Automation → **Get news tweets**). Pick a topic and how many.
2. A "News tweets" issue appears in about a minute with ready tweets. Read each one, tap **➜ Open in X**, then Post. The Open in X links work about 2 minutes after the issue appears.

**Sunday (about 20 minutes)**
1. On x.com, signed in, open your profile and tap the **X numbers** bookmark → **Review and save in Control Panel** → **Save**. (Or type the numbers in under **Log numbers**.)
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

The same secrets power **News tweets**. Without them, News tweets writes simpler template tweets around each headline.

Test it: Control Panel → **Automation** → tick "Draft 7 more days" → **Draft now**. After a minute or two, a "New AI drafts ready for review" issue appears and the drafts show under **Posts**.

Without these secrets, everything else keeps working: the weekly drafts are skipped, News tweets uses templates, and you add posts yourself in the Control Panel.

### 3. The X numbers bookmark (2 minutes, after the Control Panel is live)

Control Panel → **Import from X** has the bookmark and step-by-step instructions for computers and phones. It works in Chrome, Safari and Edge, in the browser rather than the X app. If X changes its page design and the bookmark stops finding numbers, enter them by hand under **Log numbers** until the reader is updated.

## Files

| File | Purpose |
|---|---|
| `poster.py` | Shared helpers. `python poster.py --check` validates every post against X's 280-character weighting (emoji, ₹, • and → count as 2). |
| `brief.py` | Builds a daily brief: `python brief.py --date 2026-10-09` |
| `build_console.py` | Builds the Posting Desk and the short Open-in-X pages into `site/` |
| `scripts/draft_week.py` | The AI drafter. `--dry-run` prints the prompt; `--force` drafts regardless of runway. |
| `scripts/weekly_report.py` | The weekly report |
| `scripts/news_tweets.py` | News tweets. Topics and searches are in `TOPICS` at the top; edit them freely. Used stories are remembered in `content/news.json` so they aren't repeated. |
| `dashboard/` | The Vercel Control Panel: `index.html` plus API functions in `api/` (no dependencies) |
