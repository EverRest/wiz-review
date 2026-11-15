"""A tiny in-memory GitLab REST server (stdlib only) for local end-to-end runs.

It implements exactly the endpoints wiz-review uses, with the semantics the plugin assumes:
notes and published drafts bump the MR's `updated_at`, draft notes are visible only to their owner,
`position` needs the full set of diff refs. It encodes OUR understanding of the GitLab API, so it
proves the plugin is self-consistent, not that GitLab agrees; the first run on a real instance does that.
"""
import json
import re
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

POSITION_KEYS = ("base_sha", "head_sha", "start_sha", "position_type", "new_path")


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class FakeGitLab:
    def __init__(self, tokens):
        self.tokens = dict(tokens)  # token -> username
        self.users = {u: i + 1 for i, u in enumerate(self.tokens.values())}
        self.mrs, self.notes, self.drafts, self.todos = {}, {}, {}, []
        self.requests = []
        self._id = 1000
        self.lock = threading.Lock()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.host = f"127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()

    def nid(self):
        self._id += 1
        return self._id

    # --- data helpers (also used directly by the test script) ---
    def add_mr(self, project, iid, author, source, target, base_sha, head_sha, title="MR"):
        mr = {"iid": iid, "project": project, "author": author, "reviewers": [], "source_branch": source,
              "target_branch": target, "title": title, "sha": head_sha, "state": "opened", "draft": False,
              "diff_refs": {"base_sha": base_sha, "start_sha": base_sha, "head_sha": head_sha},
              "updated_at": now()}
        self.mrs[(project, iid)] = mr
        return mr

    def add_note(self, key, author, body, position=None):
        note = {"id": self.nid(), "author": {"username": author}, "body": body, "created_at": now(),
                "system": False, "position": position, "resolvable": bool(position), "resolved": False}
        self.notes.setdefault(key, []).append(note)
        self.mrs[key]["updated_at"] = now()
        return note

    def mr_json(self, mr):
        return {**{k: mr[k] for k in ("iid", "target_branch", "source_branch", "title", "sha", "draft",
                                       "updated_at", "diff_refs", "state")},
                "web_url": f"{self.scheme}://{self.host}/{mr['project']}/-/merge_requests/{mr['iid']}",
                "author": {"username": mr["author"]},
                "reviewers": [{"username": u} for u in mr["reviewers"]]}

    scheme = "http"

    # --- HTTP ---
    def _handler(self):
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body, headers=None):
                data = json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(data)

            def _do(self, method):
                u = urlparse(self.path)
                q = {k: v[0] for k, v in parse_qs(u.query).items()}
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n)) if n else None
                user = fake.tokens.get(self.headers.get("PRIVATE-TOKEN"))
                with fake.lock:
                    fake.requests.append((method, u.path, user))
                    if not user:
                        return self._send(401, {"message": "401 Unauthorized"})
                    try:
                        code, out, hdr = fake.route(method, unquote(u.path), q, body, user)
                    except KeyError:
                        code, out, hdr = 404, {"message": "404 Not found"}, {}
                self._send(code, out, hdr)

            def do_GET(self):
                self._do("GET")

            def do_POST(self):
                self._do("POST")

            def do_PUT(self):
                self._do("PUT")

            def do_DELETE(self):
                self._do("DELETE")

        return H

    @staticmethod
    def _page(items, q):
        per, page = int(q.get("per_page", 20)), int(q.get("page", 1))
        chunk = items[(page - 1) * per: page * per]
        return chunk, ({"X-Next-Page": str(page + 1)} if page * per < len(items) else {})

    def route(self, method, path, q, body, user):
        p = path.removeprefix("/api/v4")
        if (method, p) == ("GET", "/user"):
            return 200, {"username": user, "id": self.users[user]}, {}
        if (method, p) == ("GET", "/users"):
            found = [{"id": self.users[u], "username": u} for u in self.users if u == q.get("username")]
            return 200, found, {}
        if (method, p) == ("GET", "/merge_requests"):
            mrs = [m for m in self.mrs.values() if m["state"] == q.get("state", "opened")]
            if "reviewer_username" in q:
                mrs = [m for m in mrs if q["reviewer_username"] in m["reviewers"]]
            if "author_username" in q:
                mrs = [m for m in mrs if m["author"] == q["author_username"]]
            page, hdr = self._page([self.mr_json(m) for m in mrs], q)
            return 200, page, hdr
        if method == "GET" and re.match(r"^/projects/[^/]+$", p):  # project: its default branch
            return 200, {"default_branch": "main"}, {}
        if method == "GET" and re.match(r"^/projects/[^/]+/repository/branches/", p):
            return 200, {"commit": {"id": "d" * 40}}, {}
        if method == "GET" and re.match(r"^/projects/[^/]+/repository/files/", p):  # no team file in the fake repo
            return 404, {"message": "404 File Not Found"}, {}
        m = re.match(r"^/projects/(.+?)/merge_requests(?:/(\d+))?(?:/(.*))?$", p)
        if not m:
            raise KeyError
        project, iid, rest = m.group(1), m.group(2), m.group(3)
        if iid is None:
            if method == "GET":
                mrs = [x for x in self.mrs.values() if x["project"] == project and x["source_branch"] == q.get("source_branch")]
                return 200, [self.mr_json(x) for x in mrs], {}
            if method == "POST":  # create
                new = self.add_mr(project, max([k[1] for k in self.mrs if k[0] == project] + [0]) + 1, user,
                                  body["source_branch"], body["target_branch"],
                                  self.default_shas[0], self.default_shas[1], body.get("title", ""))
                return 201, self.mr_json(new), {}
            raise KeyError
        key = (project, int(iid))
        mr = self.mrs[key]
        if rest is None:
            if method == "GET":
                return 200, self.mr_json(mr), {}
            if method == "PUT":
                if "reviewer_ids" in body:
                    by_id = {i: u for u, i in self.users.items()}
                    mr["reviewers"] = [by_id[i] for i in body["reviewer_ids"]]
                    mr["updated_at"] = now()
                return 200, self.mr_json(mr), {}
        if rest == "notes":
            if method == "GET":
                page, hdr = self._page(self.notes.get(key, []), q)
                return 200, page, hdr
            if method == "POST":
                return 201, self.add_note(key, user, body["body"]), {}
        if rest == "discussions" and method == "GET":
            discs = [{"id": f"d{n['id']}", "notes": [n]} for n in self.notes.get(key, [])]
            return 200, discs, {}
        d = re.match(r"^discussions/d(\d+)(?:/notes)?$", rest or "")
        if d:
            target = next(n for n in self.notes[key] if n["id"] == int(d.group(1)))
            if method == "POST":
                return 201, self.add_note(key, user, body["body"]), {}
            if method == "PUT":
                target["resolved"] = bool(body.get("resolved"))
                return 200, {"id": f"d{target['id']}"}, {}
        if rest == "todo" and method == "POST":  # GitLab: a To-Do for the current user on this MR
            if (user, key) in self.todos:
                return 304, {}, {}
            self.todos.append((user, key))
            return 201, {"id": self.nid()}, {}
        if rest == "draft_notes":
            mine = [d for d in self.drafts.get(key, []) if d["author"] == user]
            if method == "GET":
                page, hdr = self._page([{"id": d["id"], "note": d["note"], "position": d["position"]} for d in mine], q)
                return 200, page, hdr
            if method == "POST":
                pos = body.get("position")
                if pos and any(k not in pos for k in POSITION_KEYS):
                    return 400, {"message": f"position is missing {[k for k in POSITION_KEYS if k not in pos]}"}, {}
                draft = {"id": self.nid(), "note": body["note"], "position": pos, "author": user}
                self.drafts.setdefault(key, []).append(draft)
                return 201, {"id": draft["id"], "note": draft["note"], "position": pos}, {}
        one = re.match(r"^draft_notes/(\d+)$", rest or "")
        if one and method == "DELETE":
            self.drafts[key] = [d for d in self.drafts.get(key, []) if not (d["id"] == int(one.group(1)) and d["author"] == user)]
            return 200, {}, {}  # real GitLab: 204; a body-less 204 isn't worth the handler special case
        pub = re.match(r"^draft_notes/(\d+)/publish$", rest or "")
        if pub and method == "PUT":
            draft = next(d for d in self.drafts[key] if d["id"] == int(pub.group(1)) and d["author"] == user)
            self.drafts[key].remove(draft)
            self.add_note(key, user, draft["note"], draft["position"])
            return 200, {}, {}
        raise KeyError

    default_shas = ("0" * 40, "0" * 40)
