"""Draws the profile's "GitHub Stats" and "Top Languages" cards as SVG files in assets/.

Standard library only; the data comes from the GitHub GraphQL API through the `gh` CLI, using the
GH_TOKEN the workflow provides. Nothing is drawn if the API call fails, so the old cards stay.

With the default workflow token only public data is counted. To include private repositories,
add a personal access token as the repository secret STATS_TOKEN (the workflow prefers it).
"""
import datetime
import json
import os
import subprocess
import sys
from html import escape

USER = os.environ.get("GITHUB_USER", "bhavyasingh-sa")
OUT_DIR = "assets"

# Night Owl, the same theme as the streak card.
BG, TITLE, TEXT, ICON, MUTED = "#011627", "#c792ea", "#7fdbca", "#ffeb95", "#5f7e97"
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Sans-Serif"

QUERY = """
query($login: String!, $from: DateTime!, $prs: String!, $merged: String!, $issues: String!) {
  user(login: $login) {
    name
    contributionsCollection(from: $from) { totalCommitContributions }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    repositoriesContributedTo(first: 1, includeUserRepositories: false,
        contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]) { totalCount }
  }
  prs: search(query: $prs, type: ISSUE, first: 1) { issueCount }
  merged: search(query: $merged, type: ISSUE, first: 1) { issueCount }
  issues: search(query: $issues, type: ISSUE, first: 1) { issueCount }
}
"""


def fetch():
    year_start = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-01-01T00:00:00Z")
    out = subprocess.run(
        [
            "gh", "api", "graphql",
            "-f", f"query={QUERY}",
            "-f", f"login={USER}",
            "-f", f"from={year_start}",
            "-f", f"prs=author:{USER} is:pr is:public",
            "-f", f"merged=author:{USER} is:pr is:merged is:public -user:{USER}",
            "-f", f"issues=author:{USER} is:issue is:public",
        ],
        check=True, capture_output=True, text=True,
    ).stdout
    data = json.loads(out)
    if data.get("errors") or not data.get("data", {}).get("user"):
        raise RuntimeError(f"GraphQL error: {data.get('errors')}")
    return data["data"]


def summarise(data):
    user = data["user"]
    repos = user["repositories"]["nodes"]
    sizes, colors = {}, {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            sizes[name] = sizes.get(name, 0) + edge["size"]
            colors[name] = edge["node"]["color"] or "#8b949e"
    return {
        "name": (user["name"] or USER).strip(),
        "stars": sum(r["stargazerCount"] for r in repos),
        "commits": user["contributionsCollection"]["totalCommitContributions"],
        "prs": data["prs"]["issueCount"],
        "merged": data["merged"]["issueCount"],
        "issues": data["issues"]["issueCount"],
        "contributed": user["repositoriesContributedTo"]["totalCount"],
        "year": datetime.datetime.now(datetime.timezone.utc).year,
        "languages": sorted(sizes.items(), key=lambda kv: -kv[1]),
        "colors": colors,
    }


def svg_frame(width, height, title, desc, body):
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="t d">\n'
        f"  <title id=\"t\">{escape(title, quote=False)}</title>\n  <desc id=\"d\">{escape(desc, quote=False)}</desc>\n"
        f'  <rect x="0.5" y="0.5" rx="4.5" width="{width - 1}" height="{height - 1}" fill="{BG}"/>\n'
        f"{body}</svg>\n"
    )


def icon(kind, x, y):
    """Small 16px icons drawn with basic shapes, so no icon font or image is needed."""
    c = ICON
    if kind == "star":
        pts = "8,1.2 10,5.8 15,6.3 11.3,9.6 12.4,14.5 8,12 3.6,14.5 4.7,9.6 1,6.3 6,5.8"
        shape = f'<polygon points="{pts}" fill="{c}"/>'
    elif kind == "commit":
        shape = (f'<line x1="0.5" y1="8" x2="5" y2="8" stroke="{c}" stroke-width="1.6"/>'
                 f'<line x1="11" y1="8" x2="15.5" y2="8" stroke="{c}" stroke-width="1.6"/>'
                 f'<circle cx="8" cy="8" r="3.2" stroke="{c}" stroke-width="1.6"/>')
    elif kind == "pr":
        shape = (f'<circle cx="3.5" cy="3.2" r="1.9" stroke="{c}" stroke-width="1.5"/>'
                 f'<circle cx="3.5" cy="12.8" r="1.9" stroke="{c}" stroke-width="1.5"/>'
                 f'<circle cx="12.5" cy="12.8" r="1.9" stroke="{c}" stroke-width="1.5"/>'
                 f'<line x1="3.5" y1="5.1" x2="3.5" y2="10.9" stroke="{c}" stroke-width="1.5"/>'
                 f'<path d="M12.5 10.9 V6 C12.5 4.6 11.7 3.8 10.3 3.8 H8" stroke="{c}" stroke-width="1.5"/>')
    elif kind == "issue":
        shape = (f'<circle cx="8" cy="8" r="6.4" stroke="{c}" stroke-width="1.6"/>'
                 f'<circle cx="8" cy="8" r="1.6" fill="{c}"/>')
    else:  # repo
        shape = (f'<rect x="2.2" y="1.5" width="11.6" height="13" rx="1.6" stroke="{c}" stroke-width="1.6"/>'
                 f'<line x1="5" y1="11" x2="11" y2="11" stroke="{c}" stroke-width="1.6"/>')
    return f'  <g transform="translate({x} {y})">{shape}</g>\n'


def stats_card(s):
    rows = [
        ("star", "Total Stars Earned", s["stars"]),
        ("commit", f"Total Commits ({s['year']})", s["commits"]),
        ("pr", "Total PRs", s["prs"]),
        ("issue", "Total Issues", s["issues"]),
        ("repo", "Contributed to (last year)", s["contributed"]),
    ]
    body = (f'  <text x="25" y="35" font-family="{FONT}" font-size="18" font-weight="600" '
            f'fill="{TITLE}">{escape(s["name"], quote=False)}\'s GitHub Stats</text>\n')
    y = 62
    for kind, label, value in rows:
        body += icon(kind, 25, y - 12)
        body += (f'  <text x="52" y="{y}" font-family="{FONT}" font-size="14" font-weight="600" '
                 f'fill="{TEXT}">{escape(label)}:</text>\n')
        body += (f'  <text x="250" y="{y}" font-family="{FONT}" font-size="14" font-weight="700" '
                 f'fill="{TEXT}">{value:,}</text>\n')
        y += 26
    # A ring with the number of PRs merged into other people's projects.
    cx, cy, r = 400, 108, 42
    body += (f'  <circle cx="{cx}" cy="{cy}" r="{r}" stroke="#0e2a47" stroke-width="7"/>\n'
             f'  <circle cx="{cx}" cy="{cy}" r="{r}" stroke="{TITLE}" stroke-width="7" opacity="0.85"/>\n'
             f'  <text x="{cx}" y="{cy + 10}" text-anchor="middle" font-family="{FONT}" font-size="30" '
             f'font-weight="800" fill="{ICON}">{s["merged"]:,}</text>\n'
             f'  <text x="{cx}" y="{cy + 64}" text-anchor="middle" font-family="{FONT}" font-size="12" '
             f'font-weight="600" fill="{TEXT}">PRs merged into</text>\n'
             f'  <text x="{cx}" y="{cy + 79}" text-anchor="middle" font-family="{FONT}" font-size="12" '
             f'font-weight="600" fill="{TEXT}">other projects</text>\n')
    desc = ", ".join(f"{label}: {value}" for _, label, value in rows)
    desc += f", PRs merged into other projects: {s['merged']}"
    return svg_frame(495, 195, f"{s['name']}'s GitHub Stats", desc, body)


def langs_card(s, count=8):
    langs = s["languages"][:count]
    total = sum(size for _, size in langs) or 1
    width, pad = 495, 25
    body = (f'  <text x="{pad}" y="35" font-family="{FONT}" font-size="18" font-weight="600" '
            f'fill="{TITLE}">Most Used Languages</text>\n')
    bar_x, bar_w, bar_y = pad, width - 2 * pad, 52
    body += (f'  <clipPath id="bar"><rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="10" rx="5"/></clipPath>\n'
             f'  <g clip-path="url(#bar)">\n')
    x = bar_x
    for name, size in langs:
        w = bar_w * size / total
        body += f'    <rect x="{x:.2f}" y="{bar_y}" width="{w + 0.5:.2f}" height="10" fill="{s["colors"][name]}"/>\n'
        x += w
    body += "  </g>\n"
    col_w, row_h, start_y = (width - 2 * pad) / 2, 24, 90
    for i, (name, size) in enumerate(langs):
        cx = pad + (i % 2) * col_w
        cy = start_y + (i // 2) * row_h
        pct = 100 * size / total
        body += (f'  <circle cx="{cx + 5:.1f}" cy="{cy - 4}" r="5" fill="{s["colors"][name]}"/>\n'
                 f'  <text x="{cx + 17:.1f}" y="{cy}" font-family="{FONT}" font-size="13" font-weight="600" '
                 f'fill="{TEXT}">{escape(name)}</text>\n'
                 f'  <text x="{cx + col_w - 20:.1f}" y="{cy}" text-anchor="end" font-family="{FONT}" '
                 f'font-size="13" fill="{MUTED}">{pct:.1f}%</text>\n')
    rows = (len(langs) + 1) // 2
    height = start_y + rows * row_h + 6
    desc = ", ".join(f"{name} {100 * size / total:.1f}%" for name, size in langs)
    return svg_frame(width, height, "Most Used Languages", desc, body)


def write_if_changed(path, text):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            if f.read() == text:
                print(f"{path}: unchanged")
                return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"{path}: written")
    return True


def main():
    try:
        s = summarise(fetch())
    except Exception as err:  # keep the old cards rather than draw wrong ones
        print(f"Could not read GitHub data, leaving the cards as they are: {err}", file=sys.stderr)
        return 1
    if not s["languages"]:
        print("No language data returned, leaving the cards as they are.", file=sys.stderr)
        return 1
    os.makedirs(OUT_DIR, exist_ok=True)
    write_if_changed(os.path.join(OUT_DIR, "stats-card.svg"), stats_card(s))
    write_if_changed(os.path.join(OUT_DIR, "top-langs.svg"), langs_card(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
