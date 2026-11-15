# wiz-review: implementation status and live test plan

> **Batch 1 (v0.4.0):** away mode, delegate, inbox, workload, the EUR cost line, the built-in Jira client, the `gitlab_via` rest/mcp switch, the manual `tick` skill and the GitHub CI file were removed. Sections below that describe them are historical.

> **Batch 2 (v0.6.0):** linked git worktrees are accepted as checkouts (real clone preferred, else the newest worktree; the precheck ref is per worktree). Deleting a draft no longer creates a lesson: lessons are created only by `lessons add`. Sections below about automatic lessons are historical.

> **Batch 3 (v0.7.0):** CI gate. A review (and the author's fallback) waits for a missing/running pipeline of the head commit (bounded by `ci_wait_max_min`, one `ci-wait` marker per commit, which also counts as a pickup for the author's timer) and is blocked by a failed one (one `ci-red` marker per commit, overridden by `/wiz-review rerun` written after it). Switch: `require_green_ci`. Minor findings already went to the summary only; unchanged.

> **Batch 5 (v0.8.0):** opt-in Slack ping (`slack_webhook`: drafts ready, 10-minute autopublish reminder; no code or finding text), opt-in review lenses (`lenses`: security, tests, errors; one extra Claude pass each, merged and deduplicated, one shared cost limit), and `stats` shows a model comparison hint (only with 20+ drafts per model) and the kept-rate by familiarity level.

Spec: `docs/superpowers/specs/2026-11-13-wiz-review-design.md` (v0.2).
The first step-by-step plan (v0.1) is done. This document replaces it, because the architecture was rewritten.

## Done
- [x] `.claude-plugin/plugin.json` (0.3.0) and `marketplace.json`. `claude plugin validate` passes.
- [x] `bin/wiz_review.py`: protocol, tick, packet, diff parsing, REST client, job, metrics, launchd, doctor.
- [x] 250 tests (`python3 -m unittest tests/test_wiz_review.py`).
- [x] Skills: `request-review`, `review-replies`, `review-now`, `status`, `setup`, `tick`, `inbox`, `precheck`, `delegate`, `away`.
- [x] Two independent code reviews. The critical and important findings are fixed, with tests.
- [x] Offline e2e with real git and `claude --restricted`, plus a fake GitLab: an inline finding that follows the rule in `CLAUDE.md`,
      $0.01–0.03, 5–7 s, refs removed, the reviewer's branch unchanged.
- [x] Checked live: `--restricted` blocks reads outside the repo, and `CLAUDE.md` is loaded.
- [x] Local e2e `tests/e2e_local.py`: a fake GitLab (`tests/fake_gitlab.py`), two "machines" (separate home folders and tokens),
      and real git and `claude`. Passed: MR creation and request through REST, pickup, inline drafts with full positions,
      autopublish, `done`, author notification, reading threads, reply and resolve, `rerun` without new commits,
      fallback review, and GitLab unavailable.
      Limit: the fake encodes our understanding of the GitLab API. So this test checks that the plugin is consistent with itself,
      not that the real GitLab agrees with it. Not checked: launchd (`schedule --install`) and installation through `/plugin`.

## Not done
- [ ] Live test on `gitlab.wiz-team.com`. The machine returned 503 earlier. A VPN is probably needed. The test is postponed so that no notifications go out at night.
- [ ] Check launchd and install the plugin with `/plugin marketplace add`.
- [ ] A plugin repository in GitLab (the user creates it) and publication of the marketplace.
- [ ] The minor items deferred from spec §11.

## Live test (needs: VPN, a test project, a second account or a colleague)

Setup on both machines: `/plugin marketplace add …`, `/plugin install wiz-review@wiz-review`,
`/wiz-review:setup`, and `/wiz-review:status` (everything shows ✅). For speed, set `WIZ_REVIEW_FAST=1` in the tick's environment.

0. **Dry run first (nothing is written).** The reviewer runs `WR review --url <test MR> --dry-run`.
   Check the printed drafts: each one is on the right file and line, and the text is useful.
   Then run `WR tick --dry-run` and check the decisions. Only after that, go to step 1.
1. **Request.** The author runs `/wiz-review:request-review @reviewer` on a branch with one or two changes.
   Expected: an MR, the Reviewers field is set, and the note starts with `<!-- wiz-review:request -->`.
2. **Pickup.** The reviewer: within 2 minutes, `picked-up` appears, then `drafts-ready` and a notification.
   Check: only the reviewer sees the drafts. Each inline comment is on the right line. The reviewer's branch did not change.
   `git for-each-ref refs/wiz-review` shows nothing.
3. **Autopublish.** Do not touch anything for 30 minutes (or use `FAST`). The drafts are published, `done` appears, and the author gets a notification.
4. **Edit.** Start a new round (`/wiz-review rerun`). Edit one draft and wait. Nothing is published automatically.
5. **Manual publish or delete.** Delete one draft and publish the rest. `done` appears. The deleted draft appears in `~/.wiz-review/lessons/`.
6. **Rerun without new commits.** The reply says "no new commits". Claude does not run (`stats` shows no new review).
7. **Rerun with a new commit.** Only the new changes are reviewed.
8. **Fallback review.** Add a reviewer whose machine is off (or add no reviewer). After 30 minutes, `fallback` appears with a review note.
9. **Failure.** Temporarily break `claude` in the reviewer's PATH. `failed` appears, and one retry follows.
10. **GitLab unavailable.** Turn off the VPN. The tick writes "gitlab unavailable" and does not crash.

Most likely fixes needed: the fields `draft_notes` and `position`, whether notes update the MR's `updated_at`,
the pagination format, and the token's `api` scope.
