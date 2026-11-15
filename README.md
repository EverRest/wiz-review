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
| Local clones (or git worktrees) of the repos you will review | `git remote get-url origin` points to `gitlab.wiz-team.com`. |
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

### Step 4. Run the setup wizard
In Claude Code:
```
/wiz-review:setup
```
Claude guides you through the steps. It asks permission before each action:
1. It checks the token (`doctor`).
2. It asks **which folders hold your clones**. You can name several, for example `~/code` and `~/work`. Folders are scanned up to 3 levels deep.
   The folders are saved, and the repos it finds are listed as "project → folder". A review does not start for a project without a clone.
3. It installs the background run (launchd, every 2 minutes).

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

> 🤖 _wiz-review · Claude Code · claude-haiku-5-5_

The tag shows the tool and the model. The model is the real model id from the response, not an alias. Tokens and cost are not in the MR: they go only to your local `metrics.jsonl` (see `$WR stats`).

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
4. Writes a "request" note in the MR. The note needs three things: **why the change exists** (+ Jira key, if any), **how you tested it**, and **questions for the reviewer**.
   The note has no "where to look" hints on purpose. The reviewer must form its own opinion.
5. Optional: adds **acceptance criteria**. If the change has a Jira ticket and your Claude has the Atlassian MCP, it can read the ticket and write up to 10 short criteria. Otherwise you type them or skip. You approve the exact text before it goes into the MR. The plugin has no Jira client of its own.
   The reviewer's agent then says in its summary which criteria the change meets, misses, or cannot be checked.
6. Optional: adds **decisions and trade-offs**. Your Claude drafts them from its own session (what was tried and rejected, why this approach, known risks, up to 8 short bullets). You approve the exact text before it goes into the MR. The reviewer's agent treats them as **claims to verify** and flags any contradiction with the code.

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
| You edit, delete, or publish them | Your version stays. Deleting a draft is counted in `stats`, but it teaches the plugin nothing. To make a rule for the repo, say it yourself: `$WR lessons add` (see §7). |
| You do not touch them for 30 minutes (`autopublish_after_min`) | The plugin **publishes them itself**, under your name. You get a reminder with sound 10 minutes before. `0` turns autopublish off. The 30 minutes are always working time: nothing is published from 20:00 to 08:00 or at the weekend (`quiet_hours`). Drafts from Friday 19:50 are published on Monday at 08:30. |
| You start editing and stop | **Nothing** is published automatically. |
| You do not want to review | Remove yourself from the Reviewers list in the MR. |

Approve as usual, in GitLab. The agent never approves.

### Other commands
| Command | What it does |
|---|---|
| `/wiz-review:precheck` | A private review of your own change before the request. Nothing goes to GitLab. |
| `/wiz-review:review-now <MR url>` | Reviews any MR **now**, even without an author request. |
| `/wiz-review:status` | Checks that everything works, and shows statistics: the number of reviews, cost, and time. |
| `/wiz-review rerun` (MR comment) | Reviews the new commits again. The author or a reviewer can write it. |

### When nobody picks up the review
The reviewer turned off the laptop, is offline, or declined. After **30 minutes**, the author's machine runs the same check by itself.
The result appears as a normal comment in the MR, not as a draft.

### Rules to know
- A review starts only when **CI is not in the way** (`require_green_ci`, on by default). The reviewer's machine looks at the pipeline of the MR's head commit: if it is missing or still running, it waits (one `⏳ ci-wait` note per commit, then re-checks every 2 minutes) for up to `ci_wait_max_min` (30), then reviews anyway and says so in the "review started" note. If it **failed**, no review starts: one `🔴 ci-red` note asks to fix the pipeline and push, or to write `/wiz-review rerun` to review that commit anyway. `success`, `manual`, `skipped` and `canceled` count as "go". The ⏳ note counts as a pickup for the author's 30-minute timer, so the fallback does not start while a reviewer waits for CI. The fallback review obeys the same gate (it waits for a missing or running pipeline, never reviews a red one unless someone writes `rerun`). A project with no CI at all waits the full `ci_wait_max_min` before every review: set `require_green_ci` to `false` there.
- An MR in **Draft** status is ignored.
- If you are the author, you do not run a review of your own MR.
- A review starts only in an MR where the author left a "request" note (`/request-review`). Assigning a reviewer by hand does not create that note.
- You need a checkout where `origin` points to the project itself, not to your fork. A normal clone or a **linked git worktree** both work. If a project has several checkouts under your `roots`, the plugin uses the real clone, or else the most recently used worktree (`$WR repos` shows which). The review never changes the checkout's branch or files, but Claude reads **that checkout's own files** (its current branch, with its `CLAUDE.md`) for the code around the change. The MR's version of a file comes from the `show` command. So a worktree on an unrelated old branch gives older surrounding code and an older `CLAUDE.md`.
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
| `model_familiar` | `null` | A stronger model for the case when you wrote a large share of the recent commits to the changed files ("high" familiarity, see "Reviewer context"). `null` = not used. Set it with `config set model_familiar opus`. |
| `history_in_packet` | `10` | How many of your earlier comments on these files go to the review as examples of your taste, up to 3 of them drafts you rewrote (agent version -> your version). Your own recent commit subjects go too (up to 15). `0` turns all of it off. |
| `fix_history` | `true` | Past fix/bug/revert commits that touched the changed files go into the packet (up to 10 commits, 2500 characters, taken from the base so the MR's own commits are not in it). `false` turns it off. |
| `use_memory` | `false` | `true`: a filtered digest of your own Claude notes for this project goes into your reviews (see "What the reviewer's Claude actually knows"). Set it with `config set use_memory true`. |
| `small_diff_lines` | `60` | The limit for a "small" change, in lines. |
| `max_diff_lines` | `3000` | How many diff lines are sent to Claude. Claude reads the rest on demand. |
| `max_inline` | `20` | The maximum number of comments on specific lines. The rest go to the summary. Minor findings always go to the summary. |
| `require_green_ci` | `true` | Review only when the head commit's pipeline is not missing/running (wait) and not failed (blocked until `/wiz-review rerun`). `false` = review regardless of CI. |
| `ci_wait_max_min` | `30` | How long to wait for a missing or running pipeline before reviewing anyway. |
| `autopublish_after_min` | `30` | After how many minutes untouched drafts are published. `0` = never. Then the drafts wait until you publish them yourself. |
| `quiet_hours` | `{"start": "20:00", "end": "08:00", "weekends": true}` | No autopublish and no reminder in these hours, machine time. The reviewer always gets `autopublish_after_min` minutes of working time. Add `"tz": "Europe/Kyiv"` to use another time zone. `null` turns it off. Edit this key in `config.json` by hand. `doctor` shows the current value. |
| `critical_label` | `"wiz-review::critical"` | A label for the MR when a critical finding is **published**: by you, by autopublish, or by a fallback review. A critical draft that you deleted adds no label. Other labels stay. The plugin never removes the label: people do. `null` turns it off. If GitLab refuses the label, the review still finishes, and the log says why. |
| `notify` | `true` | Desktop notifications. |
| `slack_webhook` | `null` | A Slack incoming-webhook URL (`https://hooks.slack.com/...`) for a short ping when your drafts are ready and 10 minutes before they autopublish. See "Slack ping". `none` turns it off. |
| `lenses` | `[]` | Extra focused Claude passes after the main review, for critical repos: any of `security`, `tests`, `errors`. Set with `config set lenses security,tests` (`none` clears). **Each lens adds roughly one more review's cost.** See "Review lenses". |
| `exclude` | `[]` | Extra file patterns that are not reviewed, for example `["*.generated.md"]`. |
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
$WR doctor                             # shows the current choice in the line "models: …"
```
For one review only: `/wiz-review:review-now <url>` with a model, or `$WR review --url <url> --model opus`.
The model is chosen in this order: the model given for this review → `model_familiar` (if set, and your familiarity with the changed files is "high") → `model_small` (if set and the change is small) → `model`.
If your account cannot use the model, the MR gets a "failed" note with the hint `config set model inherit`.
Rough cost for a trivial request: `haiku` ≈ $0.001, `sonnet` ≈ $0.01, `opus` ≈ $0.02. For real changes the difference is larger.
`$WR stats` shows the actual figures for your MRs, split by model. It also shows which model's drafts people keep (see "What `stats` tells you").

### What `stats` tells you

Besides reviews, errors, tokens, cost, and time per model, `stats` reports what reviewers did with the agent's drafts, from the rounds that have closed:
```
  claude-sonnet-5-5: 36/48 agent drafts kept (75%)
  claude-haiku-5-5: 13/52 agent drafts kept (25%)
  hint: claude-sonnet-5-5: 75% kept (n=48) vs claude-haiku-5-5: 25% (n=52)
  by reviewer familiarity: high 20/24 kept (83%), medium 10/20 kept (50%), low 4/12 kept (33%)
```
- **Kept** means a draft that was published as it was, edited and published, or autopublished; a deleted draft is not kept. Numbers are per agent draft, summaries are not counted.
- The **hint** line appears only when at least two models are compared and every one has 20 or more agent drafts. Below that the numbers say nothing. The plugin never changes your settings from them: switching `model` is your decision.
- The **familiarity** split is recorded since 0.8.0 (the level goes into the metrics record and the round). Earlier rounds have no level and are left out. A low kept-rate on `low` familiarity can mean the model guesses more, or that you disagree more outside your area; the numbers do not say which.
- Kept is not the same as right. A reviewer may keep a weak comment or delete a good one. It measures how useful the drafts feel to the people who read them.

### Reviewer context: who you are in this code

Without this, the review sees only the repo (`CLAUDE.md`, docs, the diff). The model does not know that you wrote the code. Two small features give it what the repo does not hold. Both run on the reviewer's machine, use no extra tokens to compute, and show their data in the packet.

**1. Familiarity.** For each changed file the script reads the last 200 non-merge commits before the MR and counts how many have your `git config user.email`. The result is weighted by changed lines per file. New files have no history and do not count.

| Level | Share of recent commits | What changes |
|---|---|---|
| `high` | 30% or more | The packet says you know this area well, so the review is strict. If `model_familiar` is set, that model reviews. |
| `medium` | 5% to 30% | Nothing. |
| `low` | under 5% | The packet says you rarely work here. The model must say when it is unsure and use confidence `medium` instead of guessing. |
| unknown | | No line anywhere. This happens when you have no `user.email`, the clone is shallow, a file was renamed, the files are all new, or fewer than 5 commits exist. |

The summary draft gets one fixed line, not written by the model: `Reviewer familiarity with these files: high (41% of recent commits)`. In a fallback review, which runs on the author's machine, the line says `Author familiarity` and uses the author's email. The packet gets no familiarity text, and `model_familiar` is not used there. `precheck` does not use familiarity at all. The thresholds are constants in the script, not settings.

**2. History.** The packet gets, as data and never as instructions:
- the subjects of your last 15 commits to the changed files;
- up to 3 **drafts you rewrote**, as `agent version -> your version` pairs (same files first, then the same folders, newest first). When you edit a draft and publish it, the plugin saves both texts. These pairs show your wording and priorities better than any other signal;
- your earlier comments on the same files (then on files in the same folders), newest first, cut to 300 characters, and scrubbed for secrets. Comments and rewrites together are at most `history_in_packet`.

Comments are collected locally in `~/.wiz-review/history/<project>.jsonl` (the newest 300): when you publish or edit drafts, the comment as you left it is saved; deleted drafts are not. When untouched drafts are autopublished, they are saved as they were. To start with real history instead of an empty file, read your own diff comments on recent merged MRs once:
```bash
$WR history --backfill --limit 30      # run inside the repo, or add --project group/repo
```
It is safe to run again: a comment is added once, by note id or by file and text. Comments shorter than 20 characters ("done", "ok") are not kept.

Limits to know:
- Familiarity counts commits, not understanding. A person who moved or reformatted a file looks like an expert.
- The model does not see why you commented; it sees only what you wrote. Examples show your taste, but a wrong or outdated comment is repeated too. The history file is plain JSON lines: delete a line to remove a comment.
- Your own Claude settings, MCP, and Jira access are still not loaded in the review (`--restricted`). Your notes are, only if you turn on `use_memory` (next section).
- It is a pilot. Nobody has measured yet that this makes reviews better; `bench` (see "Measuring quality") checks it against the human comments on your old MRs.

### What the reviewer's Claude actually knows

The review runs in `--restricted` mode, so the model reads nothing of yours except what the plugin puts in the packet. It does not "know" the code or that you wrote it. Everything it knows about your project comes through these channels, and no others:

| Channel | Where it comes from | When |
|---|---|---|
| `CLAUDE.md` and the repo's docs | the reviewer's checkout | always |
| `.claude/review.md` | the repo | always, if the file exists |
| **Area guides** `.claude/review/*.md` | the repo, read from the **MR head** (so a guide matches the code under review) | always, for the files that match. Up to 4 guides and 8000 characters |
| **Past fixes** | `git log` of the base, for the changed files: up to 10 commits whose message mentions fix, bug, hotfix, revert or regression | always, every kind of review; `fix_history false` turns it off |
| **Author's decisions** | the "Рішення і компроміси" section of the request note | when the author wrote one; the model treats it as claims to verify |
| **Reviewer memory digest** | your own `~/.claude/projects/<project>/memory` | only with `use_memory true`, in your reviews and in `precheck`; never in a fallback |
| Familiarity, your recent commits, your earlier comments, your rewritten drafts | your clone and `~/.wiz-review/history` | your reviews |
| The diff, the author's request note, CI status, open threads, sibling repos | GitLab and `context_repos` | always |
| Rules you wrote with `lessons add` | `~/.wiz-review/lessons` | always |

Nothing else from `~/.claude` (settings, plugins, hooks, MCP, other projects' notes) is loaded.

**Area guides.** The people who own an area write a short file once, for example `.claude/review/billing.md`. An optional first line `paths: app/Billing/*, app/Invoices/*` limits the guide to MRs that change those files (`fnmatch` on the changed file names; `*` also matches `/`). A guide without that line is always included. Put there what a reviewer who knows the area would check and what usually breaks. A guide is part of the MR, so the model reads it as data and an MR author can change it: review guide changes like code.

**Reviewer memory digest.** Claude Code keeps notes about a project in `~/.claude/projects/<project>/memory`. With `use_memory true`, the plugin reads that folder itself and puts a digest in the packet; the model never gets the folder. The digest takes only notes of type `feedback` and `project` (never `user` or `reference`), at most 12 notes and about 6000 characters, newest first, with secrets, email addresses, and `/Users/<name>` paths removed. For a linked worktree with no folder of its own, the primary clone's folder is used. The model is told to use the notes as review preferences and not to quote them. The summary draft gets the line `Reviewer notes used: N`. Review the folder once before you turn this on: whatever is in a `feedback` or `project` note can reach Claude and shape a comment published under your name.

**Past fixes.** For the changed files the plugin lists the last 10 commits on the base whose message says fix, bug, hotfix, revert, or regression: short hash, date, subject, and the first two lines of the body. The model is told to look for the same mistake again. It is repo history, but commit text is free text, so it goes in as data.

**The honest limit.** This does not give the model your understanding. It gives it your written rules, your past comments, and your rewrites. Knowledge you never wrote down in one of these places stays in your head, and the review will not have it. The cheapest way to improve reviews is to write the guide for the area you own.

### Measuring quality (bench)

Nobody should trust the context features on faith. `bench` replays real merged MRs through the real review and compares what the plugin said with what people wrote:
```bash
$WR bench --project group/repo --limit 10 --yes --out with-context.json
$WR bench --project group/repo --limit 10 --yes --ablate history,memory,guides,fixes,familiarity --out without-context.json
```
It needs a local clone of the project (`$WR repos`) and the GitLab token. It takes the newest merged MRs that have at least one human **inline** comment (not by the MR author, not written by the plugin), fetches each MR's head into your clone through the usual service refs (your working tree and branch are not touched), builds the same packet a real review would, runs Claude, and compares. The comparison counts a human comment as **found** when some inline finding is on the same file within 5 lines, and a finding as **matched** when a human also commented near it. Everything is a dry run: nothing is posted, and the humans' comments and threads on those MRs are hidden from the model (otherwise "already raised" would hand it the answer).

Without `--yes` it prints the plan (MRs, model, ablations, about how many Claude runs) and asks. It costs tokens, one run per MR (more with `lenses`).

`--ablate` switches parts of the packet off: `history` (your commits, comments and rewrites), `memory`, `guides`, `fixes`, `familiarity` (the line and `model_familiar`). Run once with everything and once with all of them off, on the same MRs: the difference is what the context is worth. `--model` pins the model for both runs.

Honest limits:
- The match is a proxy. Lines drift between versions, and a human comment like "this is missing a test" has no line the model can hit. Findings that went to the summary (minor ones) are not counted.
- A small sample is noise. Ten MRs say little; repeat with other MRs before drawing a conclusion.
- The history file can already contain these very comments (for example after `history --backfill`), which flatters `history`. Use MRs newer than your backfill, or compare with `--ablate history` only on MRs you did not backfill.
- The humans' wording is not scored, only where they commented.

### Slack ping

Desktop notifications and the GitLab To-Do are easy to miss. If you set a webhook, the plugin also posts one short message to Slack:
```bash
$WR config set slack_webhook https://hooks.slack.com/services/T…/B…/…   # none = off
```
It is sent in two cases: your drafts are ready, and 10 minutes before untouched drafts autopublish. A message holds only: the project and MR number, the MR title (one line, at most 120 characters, secrets removed, Slack control characters escaped so `<!channel>` does nothing), the MR link, how many findings of each severity, and `N min to autopublish`. It never holds code, diff text, or the text of a finding. The author's fallback review and `--dry-run` runs send nothing.
The call has a 5-second timeout. If Slack is down or the URL is wrong, the log says so, and the tick and the review go on as before. Only `https://hooks.slack.com/...` addresses are accepted. The URL is a secret: `doctor` and the logs show only its last 4 characters, and the secret check stops any MR text that contains it. It lives in `config.json` (keep that file private, as you do with the token).

### Review lenses

The default review is one general pass. For repos where a miss is expensive, add narrow extra passes. After the main review, the script runs one more Claude call per lens, on the same packet and with the same model rules, each with a short focused instruction:
- `security`: missing authorization or ownership checks, injection, secrets, unsafe deserialization and file handling, tenant or event scoping leaks.
- `tests`: new behaviour or a bug fix without a test that would fail before the change, tests that assert nothing, mocks that hide the bug.
- `errors`: swallowed exceptions, fallbacks that hide failures, missing rollback or retry safety.

Findings are merged into the one review: a finding on the same file and line with a similar text is kept once (the more severe wording stays), and findings from a lens start with `[security]`, `[tests]`, or `[errors]`. The summary gets a line such as `Extra passes: security, tests.` `max_inline` applies to the merged list.
**Cost.** Each lens is roughly one more full review. Three lenses cost about four times the default. Tokens and cost of every pass are added to `metrics.jsonl` and `stats`. A lens pass that fails (bad output, timeout) costs only itself: the review is still posted, with `Failed: …` in the summary.
Lenses run only in a reviewer's review, not in the author's fallback or `precheck`. A single `haiku` pass will not replace a human on security; treat the lenses as a cheap extra net.

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
3. Optional: delete the data with `rm -rf ~/.wiz-review`. This removes the token, the settings, the logs, and the repo "lessons" (rules you wrote).

## 7. Manual commands

In the examples, `WR` is `python3 <path>/wiz_review.py`. The first line of `/wiz-review:status` shows the full path. You can also run:
```bash
WR="python3 $(find ~/.claude/plugins -name wiz_review.py | head -1)"
```

| Command | What it does |
|---|---|
| `$WR doctor` | Diagnostics: token, GitLab, `claude`, repos, schedule. |
| `$WR stats` | The number of reviews and errors, **tokens**, **cost in USD**, average time, and the split by model. Also, per model: how many agent drafts reviewers kept, a comparison hint when the data is enough, and the kept-rate by familiarity level. |
| `$WR tick` | Runs one polling pass by hand. |
| `$WR login` | Saves or replaces the token. |
| `$WR repos --root ~/code --root ~/work` | Sets the clone folders and rescans them. |
| `$WR schedule` / `schedule --install` / `schedule --remove` | Shows, installs, or removes the background run. |
| `$WR bench --project group/repo [--limit 10] [--model M] [--ablate a,b] [--yes] [--out f.json]` | Replays past merged MRs through the real review and compares its inline findings with the human comments. A dry run that costs tokens (see "Measuring quality"). |
| `$WR config set <key> <value>` | Changes a setting (`model`, `model_small`, `model_familiar`, `history_in_packet`, and others). `default` restores the default value. |
| `$WR review --url <MR url> [--model opus]` | The same as `/wiz-review:review-now`. You can set a model for this review only. |
| `$WR precheck --target <branch> [--model opus]` | The same as `/wiz-review:precheck`. Run it inside the repo. |
| `$WR suggest --target <branch>` | People who changed the same files in the last 90 days (git names and emails), as JSON. Run it inside the repo. |
| `$WR tick --dry-run` | Shows what the background run would do now: notes, publishes, reviews to start. It writes nothing and starts no review. |
| `$WR review --url <MR url> --dry-run` | Runs the real review on this machine (it costs tokens), then prints the drafts with their file and line instead of creating them. Use it to test on the real GitLab without disturbing anyone. |
| `$WR history --backfill [--project group/repo] [--limit 30]` | Reads your own diff comments on the project's recent merged MRs into your local history (see "Reviewer context"). Run it again any time; nothing is added twice. |
| `$WR lessons add --project group/repo --text "…"` | Saves a rule for the repo in your own words, for example "do not flag missing return types in tests". The only way to create a lesson. Max 500 characters; text with a secret is refused. |
| `$WR lessons list [--project group/repo]` | Shows the lessons, numbered. `used: true` marks the last 10, which go with every review, worded as rules you wrote. Lessons that older versions (before 0.6.0) saved from deleted drafts are still there and are sent as rules too: check them and `forget` the wrong ones. |
| `$WR lessons forget --project group/repo --n 3 [--n 5]` / `--all` | Removes lessons that teach the wrong thing, for example an old automatic one. |

## 8. If something goes wrong

First run `/wiz-review:status` (or `$WR doctor`). Each ❌ has a hint.

| Symptom | What to do |
|---|---|
| `GitLab not reachable`, or `gitlab unavailable` in the log | Turn on the VPN and check the access to GitLab. The background script retries in 2 minutes. |
| `401` in the log, or `token rejected` | The token expired or has no `api` scope. Create a new token and run `$WR login`. |
| The MR has a note "no local checkout" | Clone the repo into one of the `roots` folders. (`$WR repos` shows what it finds.) The review starts by itself within about 5 minutes. |
| The review does not start | Check in this order: (1) the author ran `/request-review`, and did not only assign you; (2) the MR is not Draft; (3) you are in the Reviewers list; (3b) the MR has a `⏳ ci-wait` or `🔴 ci-red` note from you: CI is still running or red, see "Rules to know" (`/wiz-review rerun` overrides red; `require_green_ci false` turns the gate off); (4) `doctor` shows no ❌; (5) the background script runs: `launchctl print gui/$(id -u)/com.wiz-team.wiz-review`; (6) the log `~/.wiz-review/logs/tick.log`. |
| The background script is not running | Run `$WR schedule --install`. If you changed the Python version or updated the plugin, run it again. |
| The MR has a note "⚠️ wiz-review failed" | The short text of the note gives the cause. Details are in `~/.wiz-review/logs/<project>__<MR number>.log`. The plugin retries once by itself. |
| Comments are a list in the summary, not on code lines | GitLab did not accept the line position, or the finding is minor. This is normal. The comments are still in the summary. |
| No notifications | On macOS, check that notifications are allowed for "Script Editor" in System Settings. On Linux, check that `notify-send` is installed. From cron, a notification may not reach your desktop session. |
| A review does something unexpected | Run `$WR tick --dry-run` to see the decisions. Run `$WR review --url <url> --dry-run` to see the drafts it would write. Neither one writes to GitLab. |
| The reviews stopped flagging a real kind of problem | A lesson (a rule you added with `lessons add`, or an automatic one from before 0.6.0) can teach the model to stay quiet. Run `$WR lessons list` and remove the wrong one with `$WR lessons forget`. |
| A review runs twice | Write to the plugin's author and attach `~/.wiz-review/logs/`. |

Logs and data are in `~/.wiz-review/`:
`logs/tick.log` (the background script), `logs/<project>__<MR>.log` (single reviews), `metrics.jsonl` (cost and time),
`config.json`, `repos.json`, `token`, `state/`, and `lessons/`.

## 9. Security and privacy

- **Token.** It is stored in `~/.wiz-review/token` (mode 0600) and only there. Claude never receives it. The protection is the same as for the MCP config.
- **Claude in a review** runs in `--restricted` mode. It can only read code inside your clone, and run the script's two read-only commands.
  Your settings, plugins, hooks, and MCP servers are not loaded in this run. Files outside the clone (`~/.ssh`, `~/.claude.json`, and others) are not accessible.
- **MR content** (the diff, the description, file names, and comments) is untrusted data for Claude. It is not instructions.
- **Before publishing**, the text is checked for tokens, keys, and secrets (GitLab, GitHub, AWS, Slack, Anthropic, private keys, and your token).
  If the plugin finds one, it publishes nothing.
- **Slack webhook** (optional) is stored in `~/.wiz-review/config.json`. Only `https://hooks.slack.com/...` is accepted. A ping holds the MR title, link, severity counts, and minutes to autopublish; no code or finding text. `doctor` and the logs show only the last 4 characters.
- **Your history** (`~/.wiz-review/history/`) holds your own comments, which are already visible in GitLab, and the before/after of drafts you rewrote. They go to Claude with the review of an MR in the same project. Commit subjects come from your clone. All are scrubbed for secrets and marked as data.
- **Your Claude notes** go to Claude only with `use_memory true`, as a filtered digest (types `feedback` and `project`, no emails, no home paths, secrets removed). The folder itself is never readable by the review.
- **Code changes** go to Claude (Anthropic) in the same way as any code in your Claude Code session.
- Git runs only with fixed commands. The plugin does not change your clone's working tree or branch. It reads the MR through separate service refs and removes them afterward.

## 10. Cost

Background polling costs nothing. You pay only for the review itself. By default the review uses `haiku`.
Measured values (a local run, a change of about 15 lines of PHP): `haiku` ≈ **$0.003 and about 9 seconds**. `sonnet` ≈ $0.01–0.03 and 5–7 seconds.
`$WR stats` shows the real figures for your MRs. To limit the cost, use the model choice (see above) and `exclude`. Every lens in `lenses` adds roughly one more review (see "Review lenses").

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
