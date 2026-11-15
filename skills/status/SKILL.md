---
name: status
description: Use when the user asks whether wiz-review works, what it costs, or why a review did not happen ("wiz-review status", "скільки коштує рев'ю", "чому не стартувало").
---

`WR` = `python3 <this skill's base directory>/../../bin/wiz_review.py`. The base directory is shown when the skill loads.

1. Run `WR doctor`. It checks the token, GitLab access, the claude CLI, the mapped repos, and the schedule.
2. Run `WR stats`. It shows reviews, errors, tokens (in and out), cost in USD and EUR, average duration, and results per model.
   The EUR value is an estimate at the `eur_per_usd` rate.
3. For one specific MR, show the last 30 lines of:
   - `~/.wiz-review/logs/<project with / replaced by __>__<iid>.log`
   - `~/.wiz-review/logs/tick.log`
4. If the user asks why a review did or did not do something, run `WR tick --dry-run`. It shows the decisions and writes nothing.
5. If the user says the reviews stopped flagging a real kind of problem, run `WR lessons list --project <project>`. Show the lessons with `used: true`. Offer `WR lessons forget --project <project> --n <number>` for a wrong one, after the user approves.
6. Summarize in a few lines. For each ❌, give the one command that fixes it.
