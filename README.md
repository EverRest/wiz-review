# wiz-review

Merge request review between Claude Code agents on different machines, through GitLab.

The author asks for a review with one command. Claude runs on the **reviewer's machine**, in the reviewer's clone of the repo. It leaves **draft comments** in the MR. The reviewer reads them, edits them, and publishes them. If nobody picks up the review within 30 minutes, the author's machine runs the same check. There are no servers and no bots. The only channel is GitLab.

> **Status: pilot.** Passes the unit and local end-to-end tests. Not yet run against the live `gitlab.wiz-team.com`.

## How it works

```
Author                          GitLab (MR)                       Reviewer
──────                          ───────────                       ────────
/wiz-review:request-review ─►  reviewer + "request" note
                                                  ◄── background tick (every 2 min, no Claude)
                               "review started"   ◄── picks it up, starts Claude in its clone
                               draft comments     ◄── (5–60 seconds)
                               "drafts ready"     ─► notification
                                                      reviewer reads, edits, publishes
                               "done"             ◄── after the reviewer publishes
```

- The background tick is plain Python. It uses no Claude tokens. Claude starts only for a review.
- Claude in a review can only read code in your clone, and run two read-only script commands. It has no GitLab access and never sees your token.
- The script checks the output for secrets before it publishes anything.
- The agent never approves, merges, or pushes.
- If nobody picks up a request within 30 minutes, the author's machine runs the review (the fallback). The result is a plain note, not drafts.

## Requirements

- macOS (background run uses launchd). Linux: use cron, see `setup`. Windows: not supported.
- Python 3.9+, git, Claude Code (logged in), access to `gitlab.wiz-team.com`.
- Local clones of the repos you review, with `origin` on `gitlab.wiz-team.com`.
- A personal GitLab token with scope **`api`**.

## Setup (about 10 minutes, once per machine)

1. **Token.** GitLab → Preferences → Access tokens → scope `api`.
2. **Install** in Claude Code:
   ```
   /plugin marketplace add <path or URL of this repo>
   /plugin install wiz-review@wiz-review
   ```
3. **Save the token** in a terminal, not in Claude (input is hidden):
   ```bash
   python3 "$(find ~/.claude/plugins -name wiz_review.py | head -1)" login
   ```
4. **Setup wizard** in Claude Code: `/wiz-review:setup`. It asks which folders hold your clones and installs the background run.
5. **Check:** `/wiz-review:status`. Everything should show ✅.

## Update and versions

Update with `/plugin update wiz-review`. Claude Code updates only when `version` in `.claude-plugin/plugin.json` changes, so every PR that changes behavior raises it.

**0.13.0:** all texts are English (STE). Reviews publish by default; run `config set auto_publish false` to check drafts first. A re-review resolves the threads that the new commits fix.

## Using it

**Author**

```
/wiz-review:request-review @colleague
```

Claude checks the branch, finds or creates the MR, sets the reviewers, and writes a request note with why the change exists, how you tested it, and questions for the reviewer. 

After new commits, write `/wiz-review rerun` as a comment in the MR. Only the new commits are reviewed.

**Reviewer**

Do nothing. Within about 2 minutes a "review started" note appears, and then drafts appear (only you can see them). Open the MR → Review → read, edit, and publish. Approve as usual in GitLab. To skip a review, remove yourself from Reviewers.

Other commands:

| Command | What it does |
|---|---|
| `/wiz-review:review-now <MR url>` | Review any MR now, without an author request. |
| `/wiz-review:status` | Check that everything works. |
| `/wiz-review rerun` (MR comment) | Review the new commits again. |

Every comment the plugin writes ends with a tag that names the tool and the model that wrote it. Colleagues must see that an agent wrote the comment. You can delete the tag line while you edit a draft.

## Settings

Defaults work out of the box. Change a value with `config set`, for example:

```bash
python3 "$(find ~/.claude/plugins -name wiz_review.py | head -1)" config set model sonnet
```

| Key | Default | What it does |
|---|---|---|
| `model` | `haiku` | Model for reviews. `inherit` = your own Claude Code model. `default` restores haiku. |
| `max_inline` | `20` | Inline drafts per review; the rest go to the summary. |
| `max_diff_lines` | `3000` | Diff lines sent in the packet; the rest is read on demand. |
| `history_in_packet` | `10` | Your recent commits to the changed files go into the packet as context; `0` = off. |
| `exclude` | `[]` | Extra glob patterns of files not to review, for example `["*.generated.md"]`. |
| `interval_sec` | `120` | Tick period in seconds (minimum 30). The scheduler stores it at install, so run the setup install step again after you change it. |
| `notify` | `true` | Desktop notification. |
| `auto_publish` | `true` | Publish the review at once. `false` = leave drafts in GitLab for you to check and publish. |
| `roots` | `["~/code"]` | Folders where your clones live. |
| `max_concurrent` | `2` | Parallel reviews on this machine. |

Lists and numbers take JSON, for example `config set exclude '["*.snap"]'`.

**Repo team file.** A repo can have `.claude/wiz-review.json` on its default branch. It can set `model`, `max_inline`, `exclude`, and `rules_always` (rules the review must check). It can only tighten your machine's settings: `exclude` is added to.

## Commands

`WR` below means `python3 <path to wiz_review.py>`; `/wiz-review:status` prints the path.

| Command | What it does |
|---|---|
| `WR doctor` | Diagnostics: token, GitLab, `claude`, repos, schedule. |
| `WR review --url <MR> [--model M]` | Review one MR now. |
| `WR config set <key> <value>` | Change a setting (see above). |
| `WR repos --root <folder>` | Set and rescan the clone folders. |
| `WR schedule [--install \| --remove]` | Show, install, or remove the background run. |
| `WR login` | Save or replace the token. |

## If something goes wrong

Run `/wiz-review:status`. Each ❌ has a hint.

| Symptom | What to do |
|---|---|
| `gitlab unavailable` in the log | Check the VPN. The background run retries in 2 minutes. |
| `401` or `token rejected` | The token expired or lacks `api`. Run `WR login` with a new token. |
| MR note "no local checkout" | Clone the repo into one of the `roots` folders. |
| The review does not start | (1) The author ran `/request-review`, not only assigned you. (2) The MR is not Draft. (3) You are in Reviewers. (4) `doctor` shows no ❌. (5) The background run is installed: `launchctl print gui/$(id -u)/com.wiz-team.wiz-review`. (6) Log: `~/.wiz-review/logs/tick.log`. |
| MR note "⚠️ wiz-review failed" | The note gives the cause. Details: `~/.wiz-review/logs/<project>__<MR>.log`. The plugin retries once. |

Logs and data are in `~/.wiz-review/`: `logs/`, `config.json`, `repos.json`, `token`, `state/`.

## Security and privacy

- **Token** is stored only in `~/.wiz-review/token` (mode 0600). Claude never receives it.
- **Claude in a review** runs with `--restricted`: it reads only your clone and cannot use your settings, plugins, hooks, or MCP servers.
- **MR content** (diff, description, comments, file names) is untrusted data for Claude, never instructions.
- **Before publishing**, the output is checked for tokens, keys, and secrets. If one is found, nothing is published.
- **Code** goes to Claude (Anthropic), the same way as in any Claude Code session.
- The plugin never changes your clone's working tree or branch.

## Cost

Polling costs nothing. You pay only for reviews. On `haiku`, a change of about 15 lines costs roughly $0.003 and about 9 seconds.

## For plugin developers

```bash
python3 -m unittest tests/test_wiz_review.py -v    # unit tests, no network
python3 tests/e2e_local.py                          # two "machines" + fake GitLab + real claude (≈ $0.05, ≈ 3 min)
PATH="$PWD/tests/stub_claude:$PATH" python3 tests/e2e_local.py   # same flow, stub claude, no cost
python3 tests/lint_plugin.py                        # plugin checks
```

Older design notes: `docs/superpowers/`.

## License

MIT. See `LICENSE`.
