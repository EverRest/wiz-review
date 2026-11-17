---
name: status
description: Use when the user asks whether wiz-review works, or why a review did not happen ("wiz-review status", "чому не стартувало").
---

`WR` = `python3 <this skill's base directory>/../../bin/wiz_review.py`. The base directory is shown when the skill loads.

1. Run `WR doctor`. It checks the token, GitLab access, the claude CLI, the mapped repos, and the schedule.
2. For one specific MR, show the last 30 lines of:
   - `~/.wiz-review/logs/<project with / replaced by __>__<iid>.log`
   - `~/.wiz-review/logs/tick.log`
3. If the user asks why a review did or did not do something, read `~/.wiz-review/logs/tick.log` and the MR notes.
4. Summarize in a few lines. For each ❌, give the one command that fixes it.
