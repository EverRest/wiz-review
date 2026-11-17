---
name: status
description: Use when the user asks whether wiz-review works, what it costs, or why a review did not happen ("wiz-review status", "скільки коштує рев'ю", "чому не стартувало").
---

`WR` = `python3 <this skill's base directory>/../../bin/wiz_review.py`. The base directory is shown when the skill loads.

1. Run `WR doctor`. It checks the token, GitLab access, the claude CLI, the mapped repos, and the schedule.
2. Run `WR stats`. It shows reviews, errors, tokens (in and out), cost in USD, average duration, and results per model.
3. For one specific MR, show the last 30 lines of:
   - `~/.wiz-review/logs/<project with / replaced by __>__<iid>.log`
   - `~/.wiz-review/logs/tick.log`
4. If the user asks why a review did or did not do something, run `WR tick --dry-run`. It shows the decisions and writes nothing.
5. Summarize in a few lines. For each ❌, give the one command that fixes it.
