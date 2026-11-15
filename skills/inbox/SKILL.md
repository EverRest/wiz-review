---
name: inbox
description: Use when the user asks where their reviews are or what waits for them ("де моє рев'ю", "що чекає на мене", "wiz-review inbox", "my reviews"). Lists the user's open MRs with their wiz-review state. Uses no tokens.
---

`WR` = `python3 <this skill's base directory>/../../bin/wiz_review.py`. The base directory is shown when the skill loads.

1. Run `WR inbox`. It returns a JSON list. Each item has `url`, `title`, `role` (`author` or `reviewer`), `state`, `waiting_on`, `age_min`, and `action`.
2. Show one line per MR, in the user's language. Put the items that have an `action` first.
   - For `reviewer`: the state, and how long ago it changed.
   - For `author`: the state per reviewer, and who the MR still waits for.
3. For each item with an `action`, give the one next step that the `action` names.
   Example: "drafts wait for you; autopublish in 12 min" means: open the MR and look at the drafts now.
4. If the list is empty, say that there are no open MRs for the user.
5. Exit code 2 or a GitLab error means GitLab cannot be reached. Say so in one line. Often the cause is the VPN.
