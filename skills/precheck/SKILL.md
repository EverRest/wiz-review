---
name: precheck
description: Use when the author wants a private review of their own change before asking colleagues ("перевір мої зміни перед рев'ю", "precheck", "self-review this branch"). Runs the same isolated review on this machine and prints the result in the terminal. Nothing is posted to GitLab.
---

`WR` = `python3 <this skill's base directory>/../../bin/wiz_review.py`. The base directory is shown when the skill loads.

1. Find the target branch. Use the git workflow in the repo's `CLAUDE.md`. If it is not there, ask the user.
2. Run `WR precheck --target <target>`.
   If the user wants one model for this check only, add `--model opus|sonnet|haiku|<full id>`.
   The command compares the current checkout with the target branch. It includes uncommitted changes. It lists untracked files so that Claude reads them too.
   It takes from a few seconds to a few minutes.
3. Show the output to the user as it is: the summary, then the findings by severity, then the cost line.
4. Offer to fix the findings in this session. Apply a change only after the user approves it.
5. When the user is ready, offer `/wiz-review:request-review`.

This check runs on the author's machine, so it has less context than a review on a maintainer's machine. It does not replace that review.
