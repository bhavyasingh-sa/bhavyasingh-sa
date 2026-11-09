import json
import os
import re
import subprocess
import sys

USER = os.environ.get("GITHUB_USER", "bhavyasingh-sa")
README = "README.md"
START = "<!-- OPEN_SOURCE:START -->"
END = "<!-- OPEN_SOURCE:END -->"


def fetch_prs():
    out = subprocess.run(
        [
            "gh", "search", "prs",
            "--author", USER,
            "--limit", "100",
            "--json", "repository,number,title,state,url,createdAt,closedAt",
        ],
        check=True, capture_output=True, text=True,
    ).stdout
    prs = json.loads(out)
    own = USER.lower() + "/"
    return [p for p in prs if not p["repository"]["nameWithOwner"].lower().startswith(own)]


def clean_title(title):
    title = re.sub(r"^\w+(\([^)]*\))?!?:\s*", "", title.strip())
    title = re.sub(r"^\[[^\]]*\]\s*", "", title)
    return title[:1].upper() + title[1:] if title else title


def status_label(state):
    if state == "merged":
        return "merged"
    if state == "open":
        return "open, awaiting review"
    return "closed"


def sort_key(pr):
    when = pr["closedAt"] if pr["state"] == "merged" else pr["createdAt"]
    return when or ""


def build(prs):
    shown = [p for p in prs if p["state"] in ("merged", "open")]
    shown.sort(key=sort_key, reverse=True)
    shown.sort(key=lambda p: p["state"] != "open")
    lines = []
    for p in shown:
        repo = p["repository"]["name"]
        lines.append(
            f"- [{repo} #{p['number']}]({p['url']}) — {clean_title(p['title'])} ({status_label(p['state'])})"
        )
    return "\n".join(lines)


def main():
    prs = fetch_prs()
    block = build(prs)
    if not block:
        print("No pull requests found, leaving README unchanged.")
        return 0

    with open(README, encoding="utf-8") as f:
        text = f.read()
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    if not pattern.search(text):
        print("Markers not found in README.", file=sys.stderr)
        return 1
    new = pattern.sub(lambda _: f"{START}\n{block}\n{END}", text)
    if new != text:
        with open(README, "w", encoding="utf-8") as f:
            f.write(new)
        print("README updated.")
    else:
        print("README already up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
