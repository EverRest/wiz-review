---
name: setup
description: One-time wiz-review onboarding on a developer machine — GitLab token check, local repo map, background tick. Use when the user says "set up wiz-review" or a note says there is no local checkout.
---

`WR` = `python3 <this skill's base directory>/../../bin/wiz_review.py`. The base directory is shown when the skill loads.

Do each step only after the user says yes.
Never ask for, print, or write the token.
Ask the user every question in the user's language.

1. **GitLab access.** Run `WR doctor`.
   If the token is missing, tell the user to run this command in their own terminal. Claude never sees the token:
   `python3 <absolute path to bin/wiz_review.py> login`
   The command asks for a personal access token with scope `api`. Input is hidden.
   It checks the token with GitLab and saves it to `~/.wiz-review/token` (mode 0600). No MCP server is needed.
   An existing user-scope `gitlab` MCP server token is reused automatically, as an alternative.
2. **Find the clone folders.** Ask: "In which folders do you keep your GitLab clones?"
   The user can name several folders. The default is `~/code`. Folders up to 3 levels deep are scanned.
   Run `WR repos --root <folder1> --root <folder2>`.
   The script saves the folders in `~/.wiz-review/config.json`. The tick rescans them by itself when a new clone appears. You do not need to run anything else.
   Show the user the repos you found (project → folder). Then tell them:
   - Review works only for these projects.
   - For other projects, the tick posts a note on the MR that says to clone the repo.
   - The tick picks up the MR as soon as the clone appears in one of these folders.

   If fewer repos appear than expected, ask for more folders.
   A clone must have `origin` on `gitlab.wiz-team.com`. A fork does not work.
3. **Choose the model and cost.** Ask the user. If the user says "ok", keep the defaults.
   - The default is **`haiku` for every diff size**. It is the cheapest and the fastest. It is weaker than `sonnet` and `opus`. For critical repos, suggest a stronger model.
   - Show the current choice. `WR doctor` prints `models: …`.
   - Offer these commands:
     - `WR config set model sonnet|opus|<full id>`
     - `WR config set model inherit` (use the user's own Claude Code model)
     - `WR config set model default` (back to haiku)
   - Other settings use the same command form: `max_concurrent`, `interval_sec`, `notify true|false`, `exclude '["*.generated.md"]'`.
   - Reviews start as soon as the reviewer is picked. Drafts are never published automatically: the reviewer publishes them by hand. Tell the user this.
4. **Install the background tick.**
   - On macOS, run `WR schedule` to print the launchd plist. After the user approves, run `WR schedule --install`.
   - On other systems, `WR schedule` prints a crontab line to add.
   - The tick is plain Python. It uses no Claude session and no tokens. Only real reviews start `claude -p`.
   - The schedule starts a small launcher, `~/.wiz-review/bin/wiz-review`. The launcher always runs the newest installed plugin version, so a plugin update needs nothing else.
5. Run `WR doctor` again. If every check shows ✅, the setup is done.
   Tell the user the absolute script path that `doctor` prints on its first line (`script: …`). The user needs this path for manual commands such as `login`.
