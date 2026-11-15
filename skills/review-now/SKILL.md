---
name: review-now
description: Use when the user wants an immediate wiz-review of a specific GitLab MR on this machine ("відрев'юй цей MR", "review !142 now"), even if nobody requested it. Starts the same background review that the tick would start, and leaves draft notes.
---

`WR` = `python3 <this skill's base directory>/../../bin/wiz_review.py`. The base directory is shown when the skill loads.

1. Get the MR URL: `https://gitlab.wiz-team.com/<project>/-/merge_requests/<iid>`.
   If the user did not give it, ask.
2. Run `WR review --url <url>`.
   If the user wants one model for this review only, add `--model opus|sonnet|haiku|<full id>`.
   Otherwise the configured models are used.
   If the output says "no local checkout", run `WR repos` and retry once.
3. Tell the user:
   - The review runs in the background. It usually takes 1 to 5 minutes.
   - The drafts appear in GitLab.
   - A desktop notification fires when they are ready.
   - The command prints the log path.
