---
name: tick
description: Run one wiz-review polling pass by hand, or keep it running in a CLI session with `/loop 2m /wiz-review:tick` on machines without launchd. Normally the tick runs from launchd and needs no Claude session at all.
---

`WR` = `python3 <this skill's base directory>/../../bin/wiz_review.py`. The base directory is shown when the skill loads.

Run `WR tick` and print its output.
If the exit code is 2, GitLab cannot be reached. Say so in one line. Often the cause is the VPN.
Do nothing else. The tick decides by itself. It posts notes and starts background reviews. It never asks questions.
