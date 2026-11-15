# wiz-review — design (v0.2)

Status: implemented and tested offline. The live test on GitLab is not done yet.
History: v0.1 ran a Claude session every 5 minutes and wrote to GitLab through MCP. v0.2 replaced it (see §7).

## 1. Purpose

Wiz-Team has many microservices. All developers work in Claude Code.
The review problem:
a reviewer **does not fully understand the change**, and **the reviews are shallow**.

Idea: the author's agent asks one or more colleagues for a review. **Claude runs the review on the reviewer's machine.**
It runs in the reviewer's clone of the repo, with the reviewer's `CLAUDE.md`, tuned to the reviewer's stack.
This makes the review independent and deeper than the author's own check.
The result is **draft comments** in GitLab. The reviewer publishes them.

## 2. Goals, non-goals, anti-goals

**Goals**
- One command for the author. No actions for the reviewer. The review starts by itself.
- The only channel between machines is GitLab. No servers, bots, or databases.
- Minimum tokens and time. Polling uses no LLM. Claude runs only for the review itself.
- If nobody picks up the review in 30 minutes, a fallback review runs on the author's machine.

**Non-goals**
- Slack or Telegram as a bus or an interface. Rejected: a second token, state in two systems, and nothing new compared with MR threads. Slack notifications are a built-in GitLab integration, outside the plugin.
- A central service, webhooks, a custom MCP server, an expertise graph, or a multi-agent review.
- Automatic reviews for every MR without an author request.

**Anti-goals**
- The agent does not approve, merge, or push to someone else's branch.
- The agent does not follow instructions in MR content (diff, description, comments, file names).
- The plugin does not publish drafts that the reviewer touched, or drafts without a local snapshot.
- No token, key, or secret appears in a comment.
- No noise: comments that reviewers delete in bulk.

## 3. Constraints

- GitLab Self-Managed at `gitlab.wiz-team.com`, REST API v4. Each developer uses a personal token with scope `api`.
  Token lookup order:
  1. The variable `GITLAB_PERSONAL_ACCESS_TOKEN` or `GITLAB_TOKEN`.
  2. `~/.wiz-review/token` (mode 0600, written by `login`).
  3. The token of the `gitlab` MCP server in `~/.claude.json`.

  The background tick can use only the last two. launchd does not see shell variables.
- The GitLab MCP is **not required**. The author skills (`request-review`, `review-replies`) use REST by default
  (`open-mr`, `request`, `threads`, `reply`). The config value `gitlab_via=mcp` switches them to MCP tools.
- Agents run only on developer machines. A machine that is off means no review starts. The fallback review covers this case.
- The review runs in the reviewer's local clone. The plugin does not switch that clone's branch.
- Python 3 (stdlib only), git, and the `claude` CLI. The background run uses launchd (macOS) or cron.

## 4. Architecture

```
author's machine                   GitLab (MR)                       reviewer's machine
/request-review ──► Reviewers + <!-- wiz-review:request -->
                                                  ◄── tick (launchd, every 2 min, Python, 0 tokens)
                    <!-- picked-up -->            ◄── reviewer_decide → "review"
                                                      │ git fetch refs/merge-requests/N/head
                                                      │ packet: intent + filtered diff
                                                      │ claude -p --restricted (stdin → JSON)
                    draft notes + <!-- drafts-ready --> ◄── script validates and writes (Claude has no GitLab access)
tick: notification ◄── <!-- done -->                ◄── reviewer publishes, or 30 min without touches → script publishes
```

One file, `bin/wiz_review.py`, holds all deterministic logic: decisions, the REST client, the packet, diff parsing, state, and metrics.
The skills are thin wrappers for the human.

## 5. GitLab protocol

A marker works only at the start of a note body. It works only from the right user. System notes are ignored.

| Marker or command | Author | Meaning |
|---|---|---|
| `<!-- wiz-review:request -->` | MR author | Review request: **Why** (+ Jira key), **How tested**, **Author's questions**. No "where to look" hints. |
| `picked-up sha=` | reviewer | The review started. |
| `drafts-ready sha=` | reviewer | Drafts are created. An @-mention triggers the notification. |
| `done sha=` | reviewer | The round is closed. It was published by hand, published automatically, or closed by a `rerun` with no new commits. |
| `failed sha=` | reviewer | The job failed. An immediate retry follows. |
| `fallback sha=` | author | The fallback review started. |
| `/wiz-review rerun` | author or reviewer | Review the new commits again. |
| `<!-- wiz-review:away -->` | a reviewer | The reviewer is away and steps aside for this request. Their machine does not review it until a new `request` or `rerun`. If all reviewers are away, the author's fallback starts at once. |
| `<!-- wiz-review:delegated -->` | a reviewer | The MR was forwarded ("not my area"). The pickup timer starts again from this marker. Only the first 2 after a request count. |

A new `request` from the author works as a `rerun`.

### Reviewer decision (`reviewer_decide`) → `review | rerun | retry | autopublish-check | None`
- The reviewer is listed as a reviewer. The MR is not a draft. The author posted a `request`.
- No `picked-up` from me → `review`.
- The round is closed (`drafts-ready` or `done` is newer than `picked-up`), and a `rerun` or a new `request` appeared → `rerun`.
- The round is open: `failed`, or 30 minutes without a result → `retry`. This happens once per round.
- `drafts-ready` is older than 30 minutes and there is no `done` → `autopublish-check`.

### Author decision (`author_decide`) → `fallback | None`
- I have a `request`. No `fallback` follows it. The MR is not a draft.
- No reviewers → fallback at once. Otherwise fallback after 30 minutes, if no reviewer is making progress.
  The 30 minutes count from the request, or from the latest of the first 2 `delegated` markers after it. So a forward gives the new reviewer time to pick up. A hand-written marker can delay the fallback by at most 2 × 30 minutes.
  A reviewer makes progress if it has `drafts-ready` or `done`, or a `picked-up` younger than 60 minutes.
  A reviewer that posted two `failed` markers after the request is not making progress.

### Autopublish
30 minutes after `drafts-ready`, the script publishes **only its own drafts**, and **only if** the reviewer did not touch them.
"Did not touch" means: the same set of ids, the same text, and no new draft from the reviewer.
The script needs a local snapshot file. Without it, the script does not publish.
After a "not touched" check, the check does not repeat.
If the reviewer published or deleted the drafts by hand, the round closes with `done`.
The deleted drafts (not the summary, and not published ones) go into the repo's "lessons".

**Quiet hours** (decision 2026-11-14: on by default, 20:00–08:00 and weekends, machine time; `quiet_hours`, `null` = off).
The reviewer always gets `autopublish_after_min` minutes outside quiet hours:
- If the drafts arrive in quiet hours, the count starts when quiet hours end.
- If the deadline falls into quiet hours, it moves to the end of quiet hours plus `autopublish_after_min`. Example: drafts on Friday at 19:50 are published on Monday at 08:30.
- The reminder comes 10 minutes before the moved deadline, and never in quiet hours.
- The `drafts-ready` note names the quiet hours, so it never promises a time that moves. `next_due` uses the moved deadline, so an unchanged MR wakes at the right moment.
- A broken setting turns quiet hours off. `doctor` reports it. A broken setting never stops a review.

**Critical label** (decision 2026-11-14: only after publication; `critical_label`, default `wiz-review::critical`, `null` = off).
- The snapshot marks each draft that holds a critical finding (confidence not low). This includes the summary, if a critical finding went there.
- Autopublish adds the label after the drafts go out, if one of them was critical. The flag is saved before the first publish, so a resumed run still knows it.
- A round that the reviewer closes by hand adds the label only if a critical draft was published, not deleted.
- A fallback review is public at once, so it adds the label at once.
- `add_labels` keeps the other labels. The plugin never removes the label. A refused label never stops the round, and the tick log names the error.

### How the reviewer learns about drafts
The agent writes its notes from the reviewer's own account. The @-mention in those notes mentions the reviewer itself. GitLab usually sends no To-Do and no email for an account's own activity.
So the plugin uses three signals:
1. `POST …/merge_requests/:iid/todo`. This creates a To-Do in GitLab. It is best effort: an error does not stop the review. For a fallback review, the To-Do goes to the author.
2. A macOS notification with sound.
3. A reminder with sound, `REMIND_BEFORE` (10) minutes before autopublish. It fires once per round. It fires only if the drafts are still untouched and the deadline has not passed.

The autopublish time is set by `autopublish_after_min` (30). A value of `0` turns autopublish off.
The live behavior of To-Dos on a real GitLab is not tested yet.

### Timers
Review: 30 minutes (retry, pickup timeout, autopublish). 60 minutes (stuck). Tick: 2 minutes. Review timeout: 25 minutes.
`WIZ_REVIEW_FAST=1` divides all timers by 30 for manual tests.

## 6. Review

1. Run `git fetch` for `refs/merge-requests/<iid>/head` and for the target branch. Store them in per-MR refs `refs/wiz-review/<iid>[-target]`.
   The reviewer's branch and working tree do not change. The script removes the refs after the job.
2. The packet (stdin) contains: the instructions, the title, the author's intent, and the filtered diff. The filtered diff drops lock, generated, minified, and snapshot files. It keeps at most `max_diff_lines`. The other files are read on demand. The repo's "lessons" are included too. All third-party content sits inside `<<<UNTRUSTED … UNTRUSTED>>>`.
   The cap keeps the riskiest files first: code and config, then tests, then docs (`risk_rank`). Inside one rank, the git order stays.
   Optional context, best effort (a failure leaves only that piece out, and the job log says why):
   - The MR description (at most 4000 characters).
   - The commit subjects and bodies of the reviewed range, from local git (`log_args`, no merges, at most 80 lines).
   - The CI status of the reviewed commit, from `head_pipeline`. For a failed pipeline: the last 30 log lines of up to two failed jobs. ANSI codes and secrets are removed.
   - "Already raised": open human threads and the agent's pending drafts, at most 30. The review must not report them again. A rerun also says which of them the new commits fix.

   For a small diff (at most `small_diff_lines` changed lines), the packet uses `git diff --function-context`, so Claude sees each changed function in full. The inline anchors always use the normal diff, so GitLab accepts the positions.
   `context_repos` maps a project to sibling projects. Their local clones are added with `--add-dir`. They stay read-only under `--restricted` (checked live: without `--add-dir` the sibling is not readable). The packet tells Claude to search them for usages of the changed public symbols. A sibling without a local clone is skipped, and the job log names it.
3. Command: `claude -p --restricted --tools Read,Grep,Glob,Bash --allowedTools …`. Bash is allowed only for the `show` and `diff` commands of this script. The command also uses `--json-schema`, `--strict-mcp-config`, and `--max-budget-usd`.
   The model is chosen in this order:
   1. The model given for this run (`review --model`).
   2. `model_small`, if it is set and the diff has at most `small_diff_lines` changed lines.
   3. `model`.

   **Default: `haiku` for every diff size.** The reason is cost and speed. Haiku is weaker than sonnet and opus. This is the user's decision from 2026-11-14.
   `model=inherit` uses the default model of Claude Code. `config set model default` sets haiku again.
   The model name is checked. It is an alias or a full id, never a flag. An unknown model gives a clear error with the hint `config set model default`.
4. Claude returns JSON: `summary` and `findings{path, line, severity, confidence, body, suggestion?}`.
   The instruction uses two passes: list candidates, verify each one, and drop what it cannot confirm.
5. The script drops invalid findings one by one. It normalizes paths. It drops `low` confidence findings. It searches for secrets. If it finds one, it publishes nothing.
   It maps findings to diff lines (`parse_diff`). It creates at most `max_inline` inline drafts. The rest, and all `minor` findings, go into the summary.
   If GitLab rejects a position, the finding stays in the summary.
6. The script creates the drafts and the `drafts-ready` note, saves a draft snapshot in a local file, and sends the notification.

The fallback review is the same job with `kind=fallback`, on the author's machine. Its result is a normal note.

### Attribution
Everything the plugin writes to GitLab carries the tag `🤖 _wiz-review · <tool> · <model>_`.
This covers each inline draft, the summary, and the fallback review. The `picked-up` and `drafts-ready` notes also name the tool and the model.
The model comes from `modelUsage` in the claude response. It is the real model id. If several models ran, the one that cost the most is used.
The tool is the constant `AGENT_TOOL`. Today it is always Claude Code. The format is ready for other runners.
The attribution is not saved in the "lessons".
The tag also shows the cost: tokens (in = normal tokens plus cache reads and writes, summed over all models; out) and the cost in USD (`total_cost_usd`, or the sum of `costUSD` over the models).
The EUR value is an estimate at the configured `eur_per_usd` rate (0.92 by default). The rate is not taken from the network.
`metrics.jsonl` stores `tokens_in`, `tokens_out`, and `cost_usd`. `stats` shows the total and the split by model, in USD and EUR.
This is the user's requirement from 2026-11-14: colleagues must always see that a machine wrote the comment, and which model did it.

### Author tools (zero tokens, except precheck)
- **Suggest reviewers** (`suggest`): from the author's local git. The changed files (committed against `origin/<target>`, plus uncommitted) → the authors of commits to those files in the last 90 days, without merges and without the author. Top 5 by number of commits. The result has git names and emails. The GitLab username is confirmed by the user, because a search by email finds only public emails for a non-admin user.
- **Inbox** (`inbox`): my open MRs as author and as reviewer, and the protocol state of each one, from the markers. For pending drafts, the time to autopublish, or "no autopublish". No LLM.
- **Precheck** (`precheck`): the target is fetched into `refs/wiz-review/precheck-target` (the user's own refs do not change; the ref is removed after the run). The diff is the working tree against the merge base, uncommitted changes included. Untracked files are listed for Claude to read. The same `--restricted` Claude runs, with Read/Grep/Glob only and no Bash. The result goes to the terminal only. Nothing is posted.

- **Acceptance criteria** (decision 2026-11-14: own Jira token, like GitLab; the author approves the text). `login --jira` saves the Jira URL, the email (Cloud: Basic auth with an API token; empty = Server/DC: Bearer with a PAT) and the token (`~/.wiz-review/jira-token`, 0600, `https` only). `jira --key` reads one issue through REST v2 with `expand=names` and returns the summary, the description, and the first text field whose name matches "acceptance" or "критер" (the field id differs per site). The skill drafts at most 10 criteria and shows the exact text. After the author approves, `request` adds the section "Критерії приймання (KEY)" (each item at most 300 characters, secret check). Without a ticket, the author can type criteria or skip. The reviewer's instructions: in the summary, say which criteria the change meets, misses, or cannot be checked. Reviews never read Jira.
- **Away mode** (decision 2026-11-14: forward if a deputy is set, else step aside). `away on [--until] [--to]` writes `~/.wiz-review/away.json`; the day after `until` counts as back. When the tick would start a review (`review`, `retry`, `rerun`), it instead forwards to the deputy with `delegate`. If there is no deputy, or the forward is refused (limit, unknown user), it posts the `away` marker once per trigger. While away, untouched drafts are not autopublished and no reminder fires; they wait until the reviewer is back (my conservative choice, not a separate decision). Limit: all of this needs the reviewer's machine to be on.
- **No MR size warning.** Decision 2026-11-14: the size of an MR is the team's matter. `request-review` does not suggest a split.
- **Delegate** (`delegate`, "not my area"): a current reviewer forwards the MR. All checks run before anything changes: a wiz-review request exists, I am a reviewer, the new person is not the author and not me, the limit is not reached, and the reason has no secret. Then the script replaces me in Reviewers with the new person and posts the `delegated` marker. The new reviewer's tick picks up the MR as usual, because the author's request already exists. My pending drafts stay private to me, and the tick no longer handles them. Decisions 2026-11-14: at most 2 forwards per request, and each forward restarts the pickup timer.

### Operations
- **Dry run.** `tick --dry-run` and `review --dry-run` wrap the GitLab client: reads go to GitLab, and each write is only recorded and printed. All local writes go to a throwaway copy of `~/.wiz-review` (mode 0700, removed afterward), so the real state, snapshots and metrics do not change. `review --dry-run` runs the real review (git and Claude). `tick --dry-run` starts no review.
- **Launcher.** `schedule` installs `~/.wiz-review/bin/wiz-review`. launchd and cron call it, not the versioned plugin path. For a plugin from the cache, it runs the newest version (versions compared as numbers). For a development checkout, it always runs that checkout. `doctor` shows which script the tick runs.
- **Fetch timeout.** Every `git fetch` has a 120-second timeout and `GIT_TERMINAL_PROMPT=0`, so a VPN problem or a credential prompt fails the job (and the protocol retries) instead of blocking it.
- **Lessons.** `lessons list` numbers all lessons and marks the last 10 (the ones in every packet). `lessons forget` removes chosen ones, or all.
- **Notifications** use `osascript` on macOS and `notify-send` on Linux. The text is always one argument, never part of a script.
- **Daily budget** (decision 2026-11-14: off by default; `max_daily_usd`). The spend is the sum of `cost_usd` in `metrics.jsonl` for the local date: every Claude run on this machine. When it is reached, the tick does not start a review or a fallback: it posts one note per MR per day, posts no `picked-up` (so the author's fallback can run from the author's budget), and wakes the MR at local midnight. `review`, `review --dry-run` and `precheck` refuse with the reason.
- **Workload.** `workload --users` counts the open MRs where each confirmed user is a reviewer (only MRs visible to the caller).

## 7. Changes from v0.1, and why

| v0.1 | v0.2 | Reason |
|---|---|---|
| A Claude session every 5 minutes | A Python tick. Claude runs only for a review. | Tokens and latency |
| Claude writes to GitLab through MCP | The script writes. Claude returns JSON. | Safety and repeatability |
| `--allowedTools` on top of the user's settings | `--restricted` | An allow-list only adds rights. The user's settings and hooks leaked into the run. The cost went from $0.18 to $0.013. |
| The draft snapshot lived in the tick's state file | A separate file with atomic writes | A race between the tick and the job |
| superpowers as the fallback review | The same isolated Claude | `Agent` and `Skill` break the isolation. In `--restricted` mode, the superpowers skill is not available (verified). The user confirmed on 2026-11-14 to keep this. If needed later: a fallback review without `--restricted`, only on the author's machine (more expensive, weaker isolation). |

## 8. Security

- Claude has only Read, Grep, and Glob inside the clone, plus two read-only subcommands of the script. It has no GitLab access and no write access.
- Git runs only with fixed, checked arguments. The diff format is fixed (`-c core.quotePath=false`, `--no-ext-diff`, `--src/dst-prefix`).
- Secrets: the plugin checks for token and key patterns and for its own token. A match raises `SecretLeak`, and nothing is published.
- Markers count only from the right user. `rerun` works only from the author or the reviewers.
- The lessons (deleted drafts) are data in an UNTRUSTED block. They are not instructions.

## 9. Metrics

`~/.wiz-review/metrics.jsonl` holds one record per review: cost, duration, turns, model, number of findings, and errors.
`~/.wiz-review/rounds.jsonl` holds one record per closed round: outcome (`human` or `auto`), model, number of agent drafts, and number deleted by the reviewer.
`stats` shows the kept rate per model. This is the pilot data for the decision on positive lessons (see §11).
`/wiz-review:status` runs `doctor` and `stats`.

## 10. Pilot

Two or three people, two weeks. Success means: reviewers publish most of the drafts. The fallback review runs rarely and only when needed.
The median review cost stays within the expected range (see `stats`).

## 11. Known limits (deferred)

- A reviewer publishes some drafts and leaves the rest. The round does not close.
- A failure in the middle of creating drafts can cause duplicates on retry.
- A retry after a failed `rerun` reviews the whole MR again. A `rerun` after the target branch was merged also reviews changes that are not the author's.
- A reviewer that comes back late reviews the MR after the fallback review.
- The cost grows with the number of reviewers.
- Live compatibility with the GitLab REST API (`draft_notes`, `position`, pagination, `updated_at`, `head_pipeline`, job logs) is not tested yet.
- Positive lessons (published drafts as good examples) are not used. Decision 2026-11-14: wait for the kept-rate data in `rounds.jsonl` from the pilot. Positive examples can make the model repeat similar findings.
