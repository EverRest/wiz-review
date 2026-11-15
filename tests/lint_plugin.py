"""Plugin metadata checks shared by GitHub and GitLab CI (stdlib only)."""
import glob
import json
import re
import sys

bad = []
for f in (".claude-plugin/plugin.json", ".claude-plugin/marketplace.json"):
    try:
        json.load(open(f))
    except Exception as e:
        bad.append(f"{f}: {e}")
for f in sorted(glob.glob("skills/*/SKILL.md")):
    m = re.match(r"---\n(.*?)\n---\n", open(f).read(), re.S)
    if not m or not re.search(r"^name:", m.group(1), re.M) or not re.search(r"^description:", m.group(1), re.M):
        bad.append(f"{f}: frontmatter needs name: and description:")
print("\n".join(bad) or "lint ok")
sys.exit(1 if bad else 0)
