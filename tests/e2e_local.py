#!/usr/bin/env python3
"""Local two-machine end-to-end: fake GitLab (tests/fake_gitlab.py) + real git + real `claude -p --restricted`.

Spends ≈ $0.05 on the Claude calls and takes ≈ 3 minutes (timers run with WIZ_REVIEW_FAST=1, i.e. /30).
It talks only to 127.0.0.1: nobody is notified, nothing touches the real GitLab.

    python3 tests/e2e_local.py
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fake_gitlab import FakeGitLab  # noqa: E402

WR = [sys.executable, str(ROOT / "bin" / "wiz_review.py")]
PROJECT = "group/demo"
failures = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        failures.append(name)


def sh(*args, cwd=None):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})


def out(*args, cwd=None):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def build_repos(tmp):
    origin = tmp / "origin.git"
    sh("git", "init", "-q", "--bare", str(origin))
    sh("git", "-C", str(origin), "symbolic-ref", "HEAD", "refs/heads/develop")
    work = tmp / "work"
    sh("git", "clone", "-q", str(origin), str(work))
    sh("git", "checkout", "-q", "-b", "develop", cwd=work)
    (work / "app").mkdir()
    (work / "app" / "Calc.php").write_text("<?php\nclass Calc {\n    public function avg(array $xs): float {\n"
                                           "        return array_sum($xs) / count($xs);\n    }\n}\n")
    (work / "CLAUDE.md").write_text("# Project rule: money values must use bcmath, never float.\n")
    sh("git", "add", "-A", cwd=work)
    sh("git", "commit", "-qm", "init", cwd=work)
    sh("git", "push", "-q", "origin", "develop", cwd=work)
    base = out("git", "rev-parse", "HEAD", cwd=work)
    sh("git", "checkout", "-q", "-b", "feat", cwd=work)
    (work / "app" / "Calc.php").write_text(
        "<?php\nclass Calc {\n    public function avg(array $xs): float {\n        return array_sum($xs) / count($xs);\n    }\n\n"
        "    public function total(array $prices): float {\n        $sum = 0.0;\n"
        "        foreach ($prices as $p) { $sum += (float) $p; }\n        return $sum;\n    }\n\n"
        "    public function find($db) {\n"
        "        return $db->query(\"SELECT * FROM carts WHERE id = \" . $_GET['id']);\n    }\n}\n")
    sh("git", "commit", "-qam", "add total", cwd=work)
    head = out("git", "rev-parse", "HEAD", cwd=work)
    for n in (1, 2):
        sh("git", "push", "-q", "origin", f"feat:refs/merge-requests/{n}/head", cwd=work)
    clones = {}
    for who in ("olena", "pavlo"):
        clones[who] = tmp / f"clone-{who}"
        sh("git", "clone", "-q", str(origin), str(clones[who]))
    return base, head, clones


class Machine:
    """One developer's machine: own WIZ_REVIEW_HOME, own token, own clone."""

    def __init__(self, name, token, clone, gl, tmp):
        self.name, self.clone = name, clone
        self.home = tmp / f"home-{name}"
        self.home.mkdir()
        (self.home / "config.json").write_text(json.dumps({"notify": False, "roots": [],
                                                           "require_green_ci": False}))  # fake has no pipelines; model: plugin default
        (self.home / "repos.json").write_text(json.dumps({PROJECT: str(clone)}))
        self.env = {**os.environ, "WIZ_REVIEW_HOME": str(self.home), "GITLAB_PERSONAL_ACCESS_TOKEN": token,
                    "WIZ_REVIEW_GITLAB_HOST": gl.host, "WIZ_REVIEW_GITLAB_SCHEME": "http", "WIZ_REVIEW_FAST": "1"}

    def wr(self, *args):
        r = subprocess.run(WR + list(args), env=self.env, capture_output=True, text=True, timeout=120)
        return r.returncode, (r.stdout + r.stderr).strip()

    def json_file(self, name, data):
        p = self.home / name
        p.write_text(json.dumps(data))
        return str(p)

    def metrics(self):
        p = self.home / "metrics.jsonl"
        return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


def wait_for(pred, timeout=180, step=3):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(step)
    return False


def bodies(gl, key):
    return [n["body"] for n in gl.notes.get(key, [])]


def has_marker(gl, key, marker):
    return any(b.startswith(f"<!-- wiz-review:{marker}") for b in bodies(gl, key))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="wiz-e2e-"))
    gl = FakeGitLab({"tok-olena": "olena", "tok-pavlo": "pavlo"})
    base, head, clones = build_repos(tmp)
    gl.default_shas = (base, head)
    olena = Machine("olena", "tok-olena", clones["olena"], gl, tmp)
    pavlo = Machine("pavlo", "tok-pavlo", clones["pavlo"], gl, tmp)
    key = (PROJECT, 1)
    print(f"workdir {tmp}\nfake GitLab on {gl.host}\n")

    # 1. author: open the MR and request a review (REST, no MCP)
    rc, o = olena.wr("open-mr", "--input", olena.json_file("mr.json", {
        "project": PROJECT, "source": "feat", "target": "develop", "title": "Add total()", "description": "d"}))
    check("author: MR created via REST", rc == 0 and json.loads(o).get("created") is True, o)
    url = json.loads(o)["url"] if rc == 0 else ""
    rc, o = olena.wr("request", "--input", olena.json_file("req.json", {
        "url": url, "why": "cart total for checkout (SEQ-1)", "tested": "manual", "questions": "",
        "reviewers": ["pavlo"]}))
    check("author: request posted, reviewer set", rc == 0 and gl.mrs[key]["reviewers"] == ["pavlo"], o)
    check("request note starts with the marker", has_marker(gl, key, "request"))

    # 2. reviewer's machine picks it up and Claude reviews in his clone
    rc, o = pavlo.wr("tick")
    check("reviewer tick: picked-up posted", has_marker(gl, key, "picked-up"), o)
    print("   waiting for the real Claude review (≈10–60 s)…")
    ok = wait_for(lambda: has_marker(gl, key, "drafts-ready") or has_marker(gl, key, "failed"))
    check("reviewer: drafts-ready posted (no failure)", ok and has_marker(gl, key, "drafts-ready"),
          next((b for b in bodies(gl, key) if "failed" in b[:30]), "timeout"))
    drafts = [d for d in gl.drafts.get(key, []) if d["author"] == "pavlo"]
    check("drafts exist and are private to the reviewer", len(drafts) >= 1 and not any(
        d["author"] == "olena" for d in gl.drafts.get(key, [])))
    inline = [d for d in drafts if d["position"]]
    check("at least one inline draft with full position", len(inline) >= 1 and inline[0]["position"]["new_path"] == "app/Calc.php",
          json.dumps(inline[:1]))
    print("   inline:", [(d["position"]["new_line"], d["note"][:90].replace("\n", " ")) for d in inline])
    print("   summary:", next((d["note"][:260].replace("\n", " ") for d in drafts if not d["position"]), "-"))
    check("reviewer got a GitLab To-Do for the ready drafts", ("pavlo", key) in gl.todos, str(gl.todos))
    check("reviewer's branch and tree untouched", out("git", "branch", "--show-current", cwd=clones["pavlo"]) == "develop"
          and out("git", "status", "--short", cwd=clones["pavlo"]) == "")
    check("service refs cleaned up", out("git", "for-each-ref", "refs/wiz-review", cwd=clones["pavlo"]) == "")
    m = pavlo.metrics()
    check("metrics recorded with cost", len(m) == 1 and not m[0].get("error") and m[0].get("cost_usd") is not None, str(m))
    check("the plugin default model (haiku) was used", m and "haiku" in (m[0].get("model") or ""), str(m))
    tag = "🤖 _wiz-review · Claude Code · " + (m[0].get("model") if m else "?") + "_"
    check("every draft ends with the tool and model tag",
          drafts and all(d["note"].rstrip().split("\n")[-1] == tag for d in drafts),
          str([d["note"][-120:] for d in drafts]))
    check("metrics carry tokens and cost", m and m[0].get("tokens_in") and m[0].get("tokens_out") and m[0].get("cost_usd") is not None, str(m))
    check("drafts-ready note names tool and model", any("Claude Code" in b and m[0].get("model", "?") in b
                                                         for b in bodies(gl, key) if b.startswith("<!-- wiz-review:drafts-ready")))
    print(f"   review cost ${m[0].get('cost_usd')}, {m[0].get('duration_s')} s, findings {m[0].get('findings')}" if m else "")

    # 3. author's tick: reviewer is progressing, no fallback
    olena.wr("tick")
    check("author tick: no fallback while reviewer works", not has_marker(gl, key, "fallback"))

    # 4. the reviewer publishes the drafts by hand -> the next tick closes the round
    for d in [d for d in gl.drafts.get(key, []) if d["author"] == "pavlo"]:
        gl.drafts[key].remove(d)
        gl.add_note(key, "pavlo", d["note"], d["position"])
    pavlo.wr("tick")
    check("human publish closes the round with a done marker", has_marker(gl, key, "done"))

    # 5. author gets told, then threads are readable
    olena.wr("tick")
    st = [json.loads(p.read_text()) for p in (olena.home / "state").glob("*.json") if "snapshot" not in p.name]
    check("author notified once about done", any(s.get("notified") for s in st), str(st))
    rc, o = olena.wr("threads", "--url", url)
    threads = json.loads(o) if rc == 0 else []
    check("author sees review threads", rc == 0 and len(threads) >= 1, o)
    if threads:
        rc, o = olena.wr("reply", "--input", olena.json_file("reply.json", {
            "url": url, "discussion": threads[0]["id"], "body": "good catch, fixing", "resolve": True}))
        check("author reply + resolve", rc == 0 and gl.notes[key][-1]["body"] == "good catch, fixing", o)
        rc, o = olena.wr("threads", "--url", url)
        check("resolved thread disappears", rc == 0 and all(t["id"] != threads[0]["id"] for t in json.loads(o)))

    # 6. rerun without new commits answers without spending Claude
    spent = len(pavlo.metrics())
    gl.add_note(key, "olena", "/wiz-review rerun")
    pavlo.wr("tick")
    time.sleep(2)
    check("rerun without new commits: answered, no Claude run",
          any("нових комітів немає" in b for b in bodies(gl, key)) and len(pavlo.metrics()) == spent)

    # 7. nobody to review -> author's machine runs the fallback review
    key2 = (PROJECT, 2)
    gl.add_mr(PROJECT, 2, "olena", "feat2", "develop", base, head, "Second")
    gl.add_note(key2, "olena", "<!-- wiz-review:request -->\n**Навіщо:** x\n**Як тестували:** y\n**Питання автора:** —")
    olena.wr("tick")
    check("fallback marker posted for MR without reviewers", has_marker(gl, key2, "fallback"))
    print("   waiting for the fallback review…")
    ok = wait_for(lambda: any(b.startswith("🤖 **Авто-рев'ю") for b in bodies(gl, key2)), timeout=180)
    check("fallback review posted as a plain note", ok, str(bodies(gl, key2)))
    fb = next((b for b in bodies(gl, key2) if b.startswith("🤖 **Авто-рев'ю")), "")
    check("fallback note names tool and model (no cost in MR text)", "🤖 _wiz-review · Claude Code · claude-" in fb.rstrip()[-140:]
          and "tokens" not in fb.rstrip()[-140:], fb[-160:])
    print("   fallback:", fb[:200].replace("\n", " "))

    # 8. GitLab outage does not crash the tick
    gl.close()
    rc, o = pavlo.wr("tick")
    check("tick survives GitLab being down (exit 2, one-line message)", rc == 2 and "unavailable" in o, f"{rc} {o}")

    print(f"\n{len(failures)} failed" if failures else "\nALL PASSED")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
