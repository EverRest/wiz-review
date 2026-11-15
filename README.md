# wiz-review

Merge request review between Claude Code agents on different machines, through GitLab.

The author asks for a review with one command. Claude runs on the **reviewer's machine**, in the reviewer's clone of the repo, with the reviewer's `CLAUDE.md`. It checks the change and leaves **draft comments** in the MR. The reviewer reads them, edits them, and publishes them. If nobody picks up the review within 30 minutes, the author's machine runs the same check. There are no servers and no bots. The only channel is GitLab.

> **Status: pilot.** The code and logic pass the tests and a local run. They are not yet tested on the live `gitlab.wiz-team.com`. If something fails, read "If something goes wrong" and contact the plugin's author.

---

## 1. How it works

```
Author (machine A)                GitLab (MR)                     Reviewer (machine B)
──────────────────                ───────────                     ────────────────────
/wiz-review:request-review ──►  reviewer + "request" note
                                                        ◄──  background script (every 2 min, no Claude)
                                "review started" note  ◄──  sees that it was assigned
                                                              starts Claude in its clone of the repo
                                draft comments         ◄──  (5–60 seconds)
                                "drafts ready" note    ─►  desktop notification
                                                              reviewer reads, edits, publishes
"review ready" notification ◄──  "done" note
```

- The two machines **do not connect to each other**. Each one talks to GitLab over HTTPS (REST API) with its own personal token.
- The background script is plain Python. It **uses no Claude tokens**. Claude starts only when there is something to review.
- Claude in the review can **only read code** in your clone. It has no access to GitLab, your keys, or other files. The script checks everything Claude returns, including secrets, before it publishes.
- The agent **never** approves, merges, or pushes to someone else's branch.

## 2. Requirements

| Requirement | How to check |
|---|---|
| macOS. The background run uses launchd. On Linux, use cron (see §3, step 5). Windows is not supported. | |
| Python 3.9+ (developed on 3.15) | `python3 --version` |
| git | `git --version` |
| Claude Code, already logged in | `claude --version`. Running `claude` in a terminal opens without a login prompt. |
| Access to `gitlab.wiz-team.com` (VPN if needed) | The site opens in a browser. |
| Local clones of the repos you will review | `git remote get-url origin` points to `gitlab.wiz-team.com`. |
| A personal GitLab token with scope **`api`** | See step 1. |

## 3. Setup, step by step (about 10 minutes, once per machine)

**Everyone does this**, the author and the reviewer. Your role depends on the MR. In one MR you are the author. In another MR you are the reviewer.

### Step 1. Create a GitLab token
1. GitLab → your avatar → **Preferences** → **Access tokens** → **Add new token**.
2. Name: `wiz-review`. Expiry date: the longest allowed.
3. Scope: only **`api`**. (`read_api` is not enough, because the plugin writes drafts and notes.)
4. Click **Create** and copy the token. GitLab shows it only once.

The token acts as you. The plugin sees only the projects you can access.

### Step 2. Install the plugin
In Claude Code, run these commands in order.

Temporary home (GitHub):
```
/plugin marketplace add EverRest/wiz-review
/plugin install wiz-review@wiz-review
```

Planned permanent home (company GitLab):
```
/plugin marketplace add https://gitlab.wiz-team.com/<group>/wiz-review.git
/plugin install wiz-review@wiz-review
```
Replace `<group>` with the group that holds the plugin repository. Ask the plugin's author.

### Step 3. Save the token
Run this in a **terminal**, not in Claude. The token then never enters the conversation:
```bash
python3 "$(find ~/.claude/plugins -name wiz_review.py | head -1)" login
```
The script asks for the token (input is hidden). It checks the token with GitLab and saves it to `~/.wiz-review/token` with mode `0600`.
A successful run prints: `saved to … ; logged in as @your_login`.

> If `find` returns nothing, the plugin was not installed in step 2. If it returns several files, any of them works.

### Step 3b. Jira token (optional, for authors)
If you want acceptance criteria from Jira in your review requests, run this in a **terminal** too:
```bash
python3 "$(find ~/.claude/plugins -name wiz_review.py | head -1)" login --jira
```
It asks for the Jira URL, your account email (Jira Cloud; leave it empty for Jira Server/Data Center), and an API token or personal access token (input hidden).
It checks the token with Jira and saves it to `~/.wiz-review/jira-token` with mode `0600`.
Create a Jira Cloud API token at id.atlassian.com → Security → API tokens. Reviews never read Jira; only your own `request-review` does.

### Step 4. Run the setup wizard
In Claude Code:
```
/wiz-review:setup
```
Claude guides you through the steps. It asks permission before each action:
1. It checks the token (`doctor`).
2. It asks **which folders hold your clones**. You can name several, for example `~/code` and `~/work`. Folders are scanned up to 3 levels deep.
   The folders are saved, and the repos it finds are listed as "project → folder". A review does not start for a project without a clone.
3. It asks how the author skills talk to GitLab: **rest** (the default; nothing else to install) or **mcp** (through your GitLab MCP server).
4. It installs the background run (launchd, every 2 minutes).

### Step 5. Linux instead of launchd
`setup` prints a crontab line. Add it with `crontab -e`.
Desktop notifications on Linux use `notify-send`. A job that cron starts often has no access to your desktop session, so the notification may not appear. The GitLab To-Do still works. Not tested on Linux yet.

### Step 6. Check
```
/wiz-review:status
```
Everything must show ✅: the token is found, GitLab is reachable, `claude` is in PATH, the repos are found, and the tick is scheduled.
The first line of the output, `script: …`, is the path to the script. You need it for manual commands (§7).

Done. You do not need to run anything else. The background script works by itself, even when Claude Code is closed.

## 4. How to use it

### The "written by a machine" tag
Everything the plugin writes to an MR **carries the tool and the model** that wrote it. The model is the real model id from the response, not an alias.

> 🤖 _wiz-review · Claude Code · claude-haiku-5-5 · 43.3k in / 529 out tokens · $0.0016 ≈ €0.0014_

The tag shows the tool, the model, **how many tokens were used** (input including cache, and output), and **the cost in USD and EUR**.
The USD value comes from the Claude response. The EUR value is an estimate at the rate in the `eur_per_usd` setting (0.92 by default). Update the rate when it changes:
`$WR config set eur_per_usd 0.95`. The `≈` sign means the EUR value is an estimate, not an invoice.

The tag appears at the end of each comment on a code line, the summary, and the fallback review. The "review started" and "drafts ready" notes also name the tool and the model.
This matters because drafts are published under **your** name, either by hand or automatically. Colleagues must see that an agent wrote the comment, and which agent. You can delete the tag line while you edit a draft before you publish it. The plugin does not mark comments that people write.

### Author
Optional first step: check your change in private.
```
/wiz-review:precheck
```
It runs the same review on your machine, against the target branch, uncommitted changes included. The result appears only in your terminal. Nothing goes to GitLab. Fix the simple problems before colleagues see them.

Then ask for the review:
```
/wiz-review:request-review @colleague1 @colleague2
```
If you name nobody, Claude suggests people who changed the same files in the last 90 days, and the `CODEOWNERS` owners. You confirm each GitLab username.
You can also ask in plain words, for example "ask @colleague for a review". Claude then:
1. Checks the branch. It asks before `git push` if the branch is not on the server yet.
2. Finds the MR, or creates it. For a new MR it asks for the target branch and the title.
3. Sets the reviewers. It uses the names you give. Otherwise it uses `CODEOWNERS`. Otherwise it asks.
4. Writes a "request" note in the MR. The note needs three things: **why the change exists** (+ Jira key), **how you tested it**, and **questions for the reviewer**.
   The note has no "where to look" hints on purpose. The reviewer must form its own opinion.
5. Optional: adds **acceptance criteria**. If the change has a Jira ticket and you ran `login --jira`, Claude reads the ticket and writes up to 10 short criteria. You approve the exact text before it goes into the MR. Without a ticket, you can type them or skip.
   The reviewer's agent then says in its summary which criteria the change meets, misses, or cannot be checked.

Then wait. When the review ends, a "Review ready" notification appears. To read the comments and fix the code:
```
/wiz-review:review-replies
```
After new commits, write `/wiz-review rerun` as a comment in the MR. Then only the **new commits** are reviewed.
Running `/request-review` again does the same thing.

### Reviewer
**Do not run anything.** When you are assigned as a reviewer, the machine starts the review by itself within about 2 minutes:
1. A "🔍 review started" note appears in the MR.
2. Within a minute or two, **drafts** appear (only you can see them) and a "drafts ready" note appears. You are notified twice:
   **a To-Do in GitLab** (works on any OS, shown in your To-Do list), and **a macOS notification with sound**.
   A note written from your own GitLab account does not create an email or a To-Do notification, so these two signals matter.
   If you have not touched the drafts before autopublish, you get one more reminder with sound.
3. Open the MR → **Review** → read, edit, delete, and publish (**Submit review**).

| What you do with the drafts | What happens |
|---|---|
| You edit, delete, or publish them | Your version stays. The plugin remembers what you deleted as "not wanted in this repo". |
| You do not touch them for 30 minutes (`autopublish_after_min`) | The plugin **publishes them itself**, under your name. You get a reminder with sound 10 minutes before. `0` turns autopublish off. The 30 minutes are always working time: nothing is published from 20:00 to 08:00 or at the weekend (`quiet_hours`). Drafts from Friday 19:50 are published on Monday at 08:30. |
| You start editing and stop | **Nothing** is published automatically. |
| You do not want to review | Remove yourself from the Reviewers list in the MR. |
| You will be on vacation | Run `/wiz-review:away` (or `$WR away on --until 2026-12-01 --to ivan`). New reviews go to your deputy, or your machine steps aside so that the author does not wait. Nothing is published in your name while you are away. This needs your machine to stay on; if it is off, the fallback review starts after 30 minutes as usual. |
| The MR is not your area | Run `/wiz-review:delegate` and name the person with more context. You leave the Reviewers list, that person joins, and the 30-minute fallback timer starts again. At most 2 forwards per request. |

Approve as usual, in GitLab. The agent never approves.

### Other commands
| Command | What it does |
|---|---|
| `/wiz-review:inbox` | Lists your open MRs and their state. It shows first what waits for you, for example "drafts wait for you; autopublish in 12 min". Uses no tokens. |
| `/wiz-review:precheck` | A private review of your own change before the request. Nothing goes to GitLab. |
| `/wiz-review:delegate` | Forwards an MR that you review to a person with more context. At most 2 forwards per request. |
| `/wiz-review:review-now <MR url>` | Reviews any MR **now**, even without an author request. |
| `/wiz-review:status` | Checks that everything works, and shows statistics: the number of reviews, cost, and time. |
| `/wiz-review:tick` | Runs one background pass by hand. Usually not needed. |
| `/wiz-review rerun` (MR comment) | Reviews the new commits again. The author or a reviewer can write it. |

### When nobody picks up the review
The reviewer turned off the laptop, is offline, or declined. After **30 minutes**, the author's machine runs the same check by itself.
The result appears as a normal comment in the MR, not as a draft.

### Rules to know
- An MR in **Draft** status is ignored.
- If you are the author, you do not run a review of your own MR.
- A review starts only in an MR where the author left a "request" note (`/request-review`). Assigning a reviewer by hand does not create that note.
- You need a **real clone** (`git clone`), where `origin` points to the project itself, not to your fork. Git worktrees do not work.
- The laptop must be on and must reach GitLab. After sleep, the background script catches up by itself.

## 5. Settings

The file `~/.wiz-review/config.json` is optional. To change a setting, use `$WR config set <key> <value>`. The command checks the value and saves it with the right type. You can also use `/wiz-review:setup`.

| Key | Default | Purpose |
|---|---|---|
| `roots` | `["~/code"]` | Folders with your clones. Usually set during setup. |
| `interval_sec` | `120` | How often the background script checks GitLab. |
| `max_concurrent` | `2` | How many reviews run at once on your machine. |
| `review_timeout_min` | `25` | After how many minutes a stuck review is stopped. |
| `model` | `"haiku"` | The model for reviews. `null` (set with `inherit`) = the default model of Claude Code. |
| `model_small` | `null` | A separate model for small changes (≤ `small_diff_lines`). If `null`, `model` is used for every size. |
| `small_diff_lines` | `60` | The limit for a "small" change, in lines. |
| `max_diff_lines` | `3000` | How many diff lines are sent to Claude. Claude reads the rest on demand. |
| `max_inline` | `20` | The maximum number of comments on specific lines. The rest go to the summary. |
| `autopublish_after_min` | `30` | After how many minutes untouched drafts are published. `0` = never. Then the drafts wait until you publish them yourself. |
| `quiet_hours` | `{"start": "20:00", "end": "08:00", "weekends": true}` | No autopublish and no reminder in these hours, machine time. The reviewer always gets `autopublish_after_min` minutes of working time. Add `"tz": "Europe/Kyiv"` to use another time zone. `null` turns it off. Edit this key in `config.json` by hand. `doctor` shows the current value. |
| `critical_label` | `"wiz-review::critical"` | A label for the MR when a critical finding is **published**: by you, by autopublish, or by a fallback review. A critical draft that you deleted adds no label. Other labels stay. The plugin never removes the label: people do. `null` turns it off. If GitLab refuses the label, the review still finishes, and the log says why. |
| `max_budget_usd` | none | A hard cost limit for one review. |
| `max_daily_usd` | none | A cost limit for all Claude runs on this machine per local day (reviews, fallbacks, prechecks). When it is reached, new reviews wait until midnight with one note in the MR, so the author's fallback review can run from the author's budget. Manual commands refuse with the reason. `doctor` shows today's spend. |
| `eur_per_usd` | `0.92` | An approximate rate, used to show the cost in EUR next to USD. |
| `notify` | `true` | Desktop notifications. |
| `exclude` | `[]` | Extra file patterns that are not reviewed, for example `["*.generated.md"]`. |
| `gitlab_via` | `"rest"` | `"rest"`: the author skills call GitLab directly. `"mcp"`: they use your GitLab MCP. |
| `context_repos` | `{}` | Sibling projects that a review may read, per project. Example: `{"group/api": ["group/web", "group/worker"]}`. Claude then checks whether a change in `group/api` breaks its consumers. Only clones that exist on your machine are used, read-only. Edit this key in `config.json` by hand; `config set` does not accept it. |

### Model choice

**The default review model is `haiku`**. It is the cheapest and the fastest model, for changes of any size. This is a deliberate choice for cost and speed.
`haiku` is weaker than `sonnet` and `opus`. On complex changes it can miss what they would catch.
For critical repos, use a stronger model. You can set a model by alias (`haiku`, `sonnet`, `opus`) or by full id:
```bash
$WR config set model sonnet            # the main model is stronger and more expensive
$WR config set model_small haiku       # small changes still use the cheapest model
$WR config set model inherit           # use your default Claude Code model
$WR config set model default           # back to the plugin default (haiku)
$WR config set model_small none        # one model for every size
$WR config set max_budget_usd 1        # a hard cost limit for one review (none = no limit)
$WR doctor                             # shows the current choice in the line "models: …"
```
For one review only: `/wiz-review:review-now <url>` with a model, or `$WR review --url <url> --model opus`.
The model is chosen in this order: the model given for this review → `model_small` (if set and the change is small) → `model`.
If your account cannot use the model, the MR gets a "failed" note with the hint `config set model inherit`.
Rough cost for a trivial request: `haiku` ≈ $0.001, `sonnet` ≈ $0.01, `opus` ≈ $0.02. For real changes the difference is larger.
`$WR stats` shows the actual figures for your MRs, split by model.

Lock files, minified code, and generated code (`*.lock`, `package-lock.json`, `*.min.js`, `*.snap`, `dist/`, `vendor/`, and others) are always skipped.

## 6. Update, disable, remove

**Update the plugin:** `/plugin marketplace update wiz-review`, then update the plugin with `/plugin`.
The background run starts through a small launcher, `~/.wiz-review/bin/wiz-review`. The launcher always runs the newest installed version, so an update needs nothing else.
Exception: a setup from before version 0.3.0 calls the script directly. Run `schedule --install` once (see §7). `doctor` warns you if this is needed.

**Disable temporarily:** `launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.wiz-team.wiz-review.plist`.
To enable it again, run `schedule --install`.

**Remove completely:**
1. Remove the background run: `schedule --remove` (see §7).
2. Remove the plugin with `/plugin`.
3. Optional: delete the data with `rm -rf ~/.wiz-review`. This removes the token, the settings, the logs, and the repo "lessons".

## 7. Manual commands

In the examples, `WR` is `python3 <path>/wiz_review.py`. The first line of `/wiz-review:status` shows the full path. You can also run:
```bash
WR="python3 $(find ~/.claude/plugins -name wiz_review.py | head -1)"
```

| Command | What it does |
|---|---|
| `$WR doctor` | Diagnostics: token, GitLab, `claude`, repos, schedule. |
| `$WR stats` | The number of reviews and errors, **tokens**, **cost in USD and EUR**, average time, and the split by model. Also, per model: how many agent drafts reviewers kept. |
| `$WR tick` | Runs one polling pass by hand. |
| `$WR login` | Saves or replaces the token. |
| `$WR login --jira` | Saves or replaces the Jira token (optional, author side). |
| `$WR jira --key SEQ-123` | Shows the ticket's summary, description, and acceptance field, as JSON. |
| `$WR repos --root ~/code --root ~/work` | Sets the clone folders and rescans them. |
| `$WR schedule` / `schedule --install` / `schedule --remove` | Shows, installs, or removes the background run. |
| `$WR config set <key> <value>` | Changes a setting (`model`, `model_small`, `max_budget_usd`, `gitlab_via`, and others). `default` restores the default value. |
| `$WR review --url <MR url> [--model opus]` | The same as `/wiz-review:review-now`. You can set a model for this review only. |
| `$WR inbox` | The same as `/wiz-review:inbox`, as JSON. |
| `$WR precheck --target <branch> [--model opus]` | The same as `/wiz-review:precheck`. Run it inside the repo. |
| `$WR suggest --target <branch>` | People who changed the same files in the last 90 days (git names and emails), as JSON. Run it inside the repo. |
| `$WR away on [--until YYYY-MM-DD] [--to user]` / `away off` / `away status` | Away mode on this machine (see the reviewer table above). |
| `$WR workload --users ivan,anna` | How many open MRs each GitLab user already reviews (only MRs you can see). |
| `$WR tick --dry-run` | Shows what the background run would do now: notes, publishes, reviews to start. It writes nothing and starts no review. |
| `$WR review --url <MR url> --dry-run` | Runs the real review on this machine (it costs tokens), then prints the drafts with their file and line instead of creating them. Use it to test on the real GitLab without disturbing anyone. |
| `$WR lessons list [--project group/repo]` | Shows the lessons (drafts that reviewers deleted), numbered. `used: true` marks the last 10, which go with every review. |
| `$WR lessons forget --project group/repo --n 3 [--n 5]` / `--all` | Removes lessons that teach the wrong thing, for example a draft that you deleted by mistake. |

## 8. If something goes wrong

First run `/wiz-review:status` (or `$WR doctor`). Each ❌ has a hint.

| Symptom | What to do |
|---|---|
| `GitLab not reachable`, or `gitlab unavailable` in the log | Turn on the VPN and check the access to GitLab. The background script retries in 2 minutes. |
| `401` in the log, or `token rejected` | The token expired or has no `api` scope. Create a new token and run `$WR login`. |
| The MR has a note "no local checkout" | Clone the repo into one of the `roots` folders. (`$WR repos` shows what it finds.) The review starts by itself within about 5 minutes. |
| The review does not start | Check in this order: (1) the author ran `/request-review`, and did not only assign you; (2) the MR is not Draft; (3) you are in the Reviewers list; (4) `doctor` shows no ❌; (5) the background script runs: `launchctl print gui/$(id -u)/com.wiz-team.wiz-review`; (6) the log `~/.wiz-review/logs/tick.log`. |
| The background script is not running | Run `$WR schedule --install`. If you changed the Python version or updated the plugin, run it again. |
| The MR has a note "⚠️ wiz-review failed" | The short text of the note gives the cause. Details are in `~/.wiz-review/logs/<project>__<MR number>.log`. The plugin retries once by itself. |
| Comments are a list in the summary, not on code lines | GitLab did not accept the line position, or the finding is minor. This is normal. The comments are still in the summary. |
| No notifications | On macOS, check that notifications are allowed for "Script Editor" in System Settings. On Linux, check that `notify-send` is installed. From cron, a notification may not reach your desktop session. |
| A review does something unexpected | Run `$WR tick --dry-run` to see the decisions. Run `$WR review --url <url> --dry-run` to see the drafts it would write. Neither one writes to GitLab. |
| The reviews stopped flagging a real kind of problem | A lesson can teach the model to stay quiet. Run `$WR lessons list` and remove the wrong one with `$WR lessons forget`. |
| A review runs twice | Write to the plugin's author and attach `~/.wiz-review/logs/`. |

Logs and data are in `~/.wiz-review/`:
`logs/tick.log` (the background script), `logs/<project>__<MR>.log` (single reviews), `metrics.jsonl` (cost and time),
`config.json`, `repos.json`, `token`, `state/`, and `lessons/`.

## 9. Security and privacy

- **Token.** It is stored in `~/.wiz-review/token` (mode 0600) and only there. Claude never receives it. The protection is the same as for the MCP config.
- **Jira token** (optional) is stored in `~/.wiz-review/jira-token` (mode 0600). Only `https://` is accepted. Only the author's machine uses it, and only to read one ticket. Acceptance criteria go into the MR only after the author approves the exact text.
- **Claude in a review** runs in `--restricted` mode. It can only read code inside your clone, and run the script's two read-only commands.
  Your settings, plugins, hooks, and MCP servers are not loaded in this run. Files outside the clone (`~/.ssh`, `~/.claude.json`, and others) are not accessible.
- **MR content** (the diff, the description, file names, and comments) is untrusted data for Claude. It is not instructions.
- **Before publishing**, the text is checked for tokens, keys, and secrets (GitLab, GitHub, AWS, Slack, Anthropic, private keys, and your token).
  If the plugin finds one, it publishes nothing.
- **Code changes** go to Claude (Anthropic) in the same way as any code in your Claude Code session.
- Git runs only with fixed commands. The plugin does not change your clone's working tree or branch. It reads the MR through separate service refs and removes them afterward.

## 10. Cost

Background polling costs nothing. You pay only for the review itself. By default the review uses `haiku`.
Measured values (a local run, a change of about 15 lines of PHP): `haiku` ≈ **$0.003 and about 9 seconds**. `sonnet` ≈ $0.01–0.03 and 5–7 seconds.
`$WR stats` shows the real figures for your MRs. To limit the cost, use `max_budget_usd`, the model choice (see above), and `exclude`.

## 11. For plugin developers

```bash
python3 -m unittest tests/test_wiz_review.py -v     # unit tests (no network)
python3 tests/e2e_local.py                           # two "machines" + a fake GitLab on localhost + a real claude (≈ $0.05, ≈ 3 minutes)
claude plugin validate .                             # plugin check
WIZ_REVIEW_FAST=1 python3 bin/wiz_review.py tick     # divides all timers by 30
```
Design: `docs/superpowers/specs/2026-11-13-wiz-review-design.md`. Status and the live test plan: `docs/superpowers/plans/2026-11-13-wiz-review.md`.

## 12. License

MIT. See `LICENSE`.
