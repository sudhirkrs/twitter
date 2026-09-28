# @Sudhirkrs17 growth engine

A plan and an automated posting pipeline to grow [@Sudhirkrs17](https://x.com/Sudhirkrs17) to 10,000+ followers.

| File | What it is |
|---|---|
| [`STRATEGY.md`](STRATEGY.md) | The full plan: positioning, profile, content pillars, the daily reply routine, milestones |
| [`content/queue.json`](content/queue.json) | 21 days of ready-to-post content (42 posts: 11 threads, 2 polls), 2 posts a day |
| [`poster.py`](poster.py) | Posts due items to X. Handles threads, polls, and resuming a half-posted thread. |
| [`.github/workflows/post.yml`](.github/workflows/post.yml) | Runs the poster at 08:30 and 19:30 IST, every day |
| [`tracking/growth-log.csv`](tracking/growth-log.csv) | Weekly numbers. Fill it in every Sunday. |

## Going live (about 20 minutes, one time)

1. **Read and edit the content.** Open `content/queue.json` and make every post sound like you. Anything written as "I/my" is a draft opinion, so change it to your real view.
2. **Set the start date.** In `content/queue.json`, set `"start_date"` (currently `2026-10-01`). Day 1 posts at 08:30 IST on that date.
3. **Get X API keys.** At [developer.x.com](https://developer.x.com), create a project and app. Set **User authentication → App permissions → Read and write**, *then* generate the **Access Token and Secret**. Tokens made before you switch to read+write can't post. Check that your API tier allows about 60 posts a month (2/day plus thread parts); thread replies count as posts.
4. **Add GitHub secrets.** In the repo, go to **Settings → Secrets and variables → Actions → Secrets** and add `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN` and `X_ACCESS_TOKEN_SECRET`.
5. **Test.** Under **Actions → Post to X → Run workflow**, leave "Dry run" ticked. The log shows what would be posted. This only works once step 6 is done, because the job is gated.
6. **Turn it on.** Go to **Settings → Secrets and variables → Actions → Variables** and add `X_POSTING_ENABLED` = `true`.
7. **Merge this branch into `main`.** Scheduled workflows only run from the default branch.

To pause, set `X_POSTING_ENABLED` to `false`.

## How the poster behaves

- Each run posts **at most one** due item (`--max` changes this), so a delayed run never floods your timeline.
- Items more than 36 hours overdue are **skipped**, not dumped all at once.
- Posted tweet IDs are saved to `state/posted.json` and committed back, so nothing is posted twice.
- If a thread fails halfway, the next run continues it from the last posted part.
- `--check` rejects any post over 280 characters using X's weighting: emoji, `₹`, `•` and `→` count as 2.

## Local use

```bash
pip install -r requirements.txt
python poster.py --check                                  # validate all posts
python poster.py --list                                   # full schedule, ✓ = posted
python poster.py --dry-run --now 2026-10-01T03:05:00+00:00  # preview a given moment
```

## Adding more content

Add entries to `posts` in `content/queue.json`, continuing the day numbers (22, 23, …). Use `"slot": "am"` or `"pm"` and `"type"` set to `tweet`, `thread` or `poll`. Each string in `parts` is one tweet, and a thread is several parts. Run `python poster.py --check` before committing.
