# @Sudhirkrs17 growth engine

A plan and a daily posting routine to grow [@Sudhirkrs17](https://x.com/Sudhirkrs17) to 10,000+ followers. **No paid X API is needed.** You post with one tap each day, and everything else is prepared for you.

| File | What it is |
|---|---|
| [`STRATEGY.md`](STRATEGY.md) | The full plan: positioning, profile, content pillars, the daily reply routine, milestones |
| [`content/queue.json`](content/queue.json) | 21 days of ready-to-post content (42 posts: 11 threads, 2 polls), 2 posts a day |
| **Posting Desk** ([open](https://claude.ai/artifact/GMpn5mq6D3S7M4dX9MeD22)) | Phone-friendly page: pick a day, tap **Open in X** (composer opens pre-filled), and **Copy** thread parts. Generated from the queue by `build_console.py`. |
| [`.github/workflows/daily-brief.yml`](.github/workflows/daily-brief.yml) | Every day at 07:45 IST, opens a GitHub issue (your reminder) with that day's posts and a link to the Posting Desk |
| [`brief.py`](brief.py) | Builds that daily brief. `python brief.py --date 2026-10-01` previews any day. |
| [`poster.py`](poster.py) | `--check` validates every post against X's 280-character weighting. It can also post through the X API if you ever get paid access. |
| [`tracking/growth-log.csv`](tracking/growth-log.csv) | Weekly numbers. Fill it in every Sunday. |

## Daily flow (about 5 minutes of posting)

1. **07:45 IST**: a GitHub notification arrives: "Posts for Thu 01 Oct 2026".
2. **08:30**: open the Posting Desk and tap **Open in X** on the morning post. The X app or website opens with the text filled in. Tap Post. (Links inside the GitHub app don't open X reliably, so always post from the Posting Desk.)
   - **Threads**: post part 1, then open it, tap Reply, and paste part 2 (Copy button). Repeat for each part. In the X composer you can also tap **+** to add all parts before posting.
   - **Polls**: X's share links can't carry poll options, so create the poll in the app using the options shown.
3. **19:30**: same for the evening post.
4. Tick **Posted** on the Posting Desk to track progress.
5. Spend the rest of your 45 minutes on replies (see `STRATEGY.md` §3). That's where the growth comes from.

**Batch option:** if your X composer shows a **Schedule** (calendar) icon, you can sit down on Sunday and schedule the whole week's single tweets from the Posting Desk in about 15 minutes. X decides which accounts get scheduling, so check whether yours has it.

## One-time setup (2 minutes)

1. **Set the start date** in `content/queue.json` (`"start_date"`, currently `2026-10-01`). Then run `python build_console.py` and republish the page, or ask Claude to.
2. **Merge this branch into `main`.** Scheduled workflows only run from the default branch.
3. **Get the notifications**: on the repo page, set **Watch → All Activity**, and install the GitHub mobile app for push notifications. The issue is also assigned to you.
4. Optional: run **Actions → Daily posting brief → Run workflow** once to see a sample issue.

## Adding more content

Add entries to `posts` in `content/queue.json`, continuing the day numbers (22, 23, …). Use `"slot": "am"` or `"pm"` and `"type"` set to `tweet`, `thread` or `poll`. Each string in `parts` is one tweet. Then run:

```bash
python poster.py --check      # every post under 280 weighted chars
python build_console.py       # regenerate the Posting Desk page
```
