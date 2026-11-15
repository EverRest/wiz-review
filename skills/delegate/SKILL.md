---
name: delegate
description: Use when a reviewer says an MR is not their area or wants to hand it to someone with more context ("не моя зона", "передай рев'ю @ivan", "delegate this review"). Replaces the user with another reviewer and restarts the pickup timer.
---

`WR` = `python3 <this skill's base directory>/../../bin/wiz_review.py`. The base directory is shown when the skill loads.

Do not put secrets in any text you write.
Put free text only in JSON files. Write them with the Write tool to `~/.wiz-review/tmp/`.

1. Get the MR URL. If the user did not give it, ask.
2. Get the GitLab username of the new reviewer.
   If the user does not know who to choose, read `CODEOWNERS` in the local clone for the changed files, and suggest the owners.
   Never pick a reviewer without the user's approval.
3. Ask for a short reason. It is optional. Example: "billing is Ivan's area".
4. Write `~/.wiz-review/tmp/delegate.json` as `{"url": <url>, "to": <username>, "reason": <text>}`.
   Run `WR delegate --input <file>`.
5. Read the result:
   - `reviewers`: the new list of reviewers.
   - `left`: how many more forwards this request allows (the limit is 2 per request).
   - `pending_drafts`: drafts that this machine already made for the user on this MR. They stay private to the user. The tick no longer publishes them. Tell the user to publish or delete them in GitLab.
6. If the output starts with `error: …`, tell the user the reason in one line:
   - No wiz-review request: the author must run `request-review` first.
   - Not a reviewer: only a current reviewer can forward.
   - Limit reached: ask the author to pick a reviewer, or let the fallback review run.
7. Tell the user: the new reviewer's machine starts the review within about 2 minutes. If nobody picks it up within 30 minutes, the author's machine runs the fallback review.
