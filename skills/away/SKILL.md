---
name: away
description: Use when the user will be away and must not get reviews, or is back ("я у відпустці до 1 грудня", "передавай рев'ю @ivan поки мене нема", "I'm back", "away mode"). Turns wiz-review's away mode on or off on this machine.
---

`WR` = `python3 <this skill's base directory>/../../bin/wiz_review.py`. The base directory is shown when the skill loads.

1. Find out what the user wants:
   - **Away.** Ask for the last day away (`YYYY-MM-DD`), or none: then away mode stays on until the user turns it off.
     Ask for a deputy (a GitLab username), or none.
   - **Back.** Turn away mode off.
   - **Status.** Show the current state.
2. Run one command:
   - Away: `WR away on [--until <YYYY-MM-DD>] [--to <username>]`
   - Back: `WR away off`
   - Status: `WR away status`
3. Tell the user what happens now:
   - New reviews for the user are forwarded to the deputy (at most 2 forwards per request), or the user steps aside with an `away` note in the MR. The author's machine then does not wait for the user. If all reviewers are away, its fallback review starts at once.
   - Untouched drafts that already wait are not published while the user is away. They go out after the user is back, by the usual rules.
   - This works only while this machine is on and can reach GitLab. If the machine is off, the usual rule applies: the fallback review starts after 30 minutes.
   - The day after `--until`, away mode ends by itself.
