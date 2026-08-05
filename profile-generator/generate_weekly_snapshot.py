import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

API = "https://api.github.com"
GRAPHQL = "https://api.github.com/graphql"
START = "<!-- WEEKLY-SNAPSHOT:START -->"
END = "<!-- WEEKLY-SNAPSHOT:END -->"


def request_json(url: str, token: str | None = None) -> object:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "dedipya-weekly-profile-snapshot",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def graphql(query: str, variables: dict, token: str) -> dict:
    request = urllib.request.Request(
        GRAPHQL,
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "dedipya-weekly-profile-snapshot",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read())
    if result.get("errors"):
        raise RuntimeError(json.dumps(result["errors"], indent=2))
    return result["data"]


def account_metrics(username: str, token: str, since: str) -> dict[str, int]:
    query = """
    query($created: String!, $merged: String!, $reviewed: String!, $approved: String!) {
      created: search(type: ISSUE, query: $created) { issueCount }
      merged: search(type: ISSUE, query: $merged) { issueCount }
      reviewed: search(type: ISSUE, query: $reviewed) { issueCount }
      approved: search(type: ISSUE, query: $approved) { issueCount }
    }
    """
    variables = {
        "created": f"is:pr author:{username} created:>={since}",
        "merged": f"is:pr author:{username} is:merged merged:>={since}",
        "reviewed": f"is:pr reviewed-by:{username} updated:>={since}",
        "approved": f"is:pr reviewed-by:{username} review:approved updated:>={since}",
    }
    data = graphql(query, variables, token)
    return {key: data[key]["issueCount"] for key in data}


def recent_projects(username: str, featured: set[str], token: str) -> list[dict]:
    repos = request_json(
        f"{API}/users/{username}/repos?per_page=100&sort=updated&direction=desc",
        token,
    )
    return [repo for repo in repos if repo["name"] in featured][:4]


def issue_counts(username: str, token: str) -> tuple[int, int]:
    open_query = urllib.parse.quote(f"user:{username} is:issue is:open")
    closed_query = urllib.parse.quote(f"user:{username} is:issue is:closed")
    opened = request_json(f"{API}/search/issues?q={open_query}", token)["total_count"]
    closed = request_json(f"{API}/search/issues?q={closed_query}", token)["total_count"]
    return opened, closed


def latest_release(username: str, projects: list[dict], token: str) -> str | None:
    for project in projects:
        try:
            release = request_json(
                f"{API}/repos/{username}/{project['name']}/releases/latest", token
            )
            return f"[{project['name']} {release['tag_name']}]({release['html_url']})"
        except Exception:
            continue
    return None


def render(config: dict, metrics: dict[str, int], projects: list[dict], open_issues: int, closed_issues: int, release: str | None) -> str:
    local_now = datetime.now(ZoneInfo(config["timezone"]))
    lines = [
        START,
        "## Weekly Engineering Snapshot",
        "",
        f"_Last refreshed: {local_now.strftime('%d %B %Y, %I:%M %p IST')}_",
        "",
        "### Current focus",
        "",
    ]
    lines.extend(f"- {item}" for item in config["current_focus"])
    lines.extend([
        "",
        "### Activity from the last 7 days",
        "",
        f"- Pull requests created: **{metrics['created']}**",
        f"- Pull requests merged: **{metrics['merged']}**",
        f"- Pull requests reviewed: **{metrics['reviewed']}**",
        f"- Pull requests approved: **{metrics['approved']}**",
        "",
        "### Recently updated projects",
        "",
    ])
    if projects:
        for repo in projects:
            description = repo.get("description") or "Engineering project and technical exploration."
            updated = datetime.fromisoformat(repo["updated_at"].replace("Z", "+00:00")).strftime("%d %b %Y")
            lines.append(f"- [{repo['name']}]({repo['html_url']}) — {description} _(updated {updated})_")
    else:
        lines.append("- No featured repository updates were found this week.")
    lines.extend([
        "",
        "### Engineering backlog",
        "",
        f"- Open issues: **{open_issues}**",
        f"- Closed issues: **{closed_issues}**",
        "",
        "### Latest release",
        "",
        f"- {release or 'No published release found in the featured repositories yet.'}",
        "",
        "> Activity combines personal projects and professional engineering work. Private repositories, source code, and confidential details remain hidden.",
        END,
    ])
    return "\n".join(lines)


def main() -> None:
    config = json.loads(Path("profile-generator/config.json").read_text(encoding="utf-8"))
    personal_token = os.environ.get("PERSONAL_GITHUB_TOKEN") or os.environ["GITHUB_TOKEN"]
    work_token = os.environ.get("WORK_GITHUB_TOKEN")
    since = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()

    totals = {"created": 0, "merged": 0, "reviewed": 0, "approved": 0}
    accounts = [(config["personal_username"], personal_token)]
    if work_token:
        accounts.append((config["work_username"], work_token))

    for username, token in accounts:
        values = account_metrics(username, token, since)
        for key in totals:
            totals[key] += values[key]

    projects = recent_projects(
        config["personal_username"], set(config["featured_repositories"]), personal_token
    )
    opened, closed = issue_counts(config["personal_username"], personal_token)
    release = latest_release(config["personal_username"], projects, personal_token)
    generated = render(config, totals, projects, opened, closed, release)

    readme_path = Path("README.md")
    readme = readme_path.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(START) + ".*?" + re.escape(END), re.DOTALL)
    if pattern.search(readme):
        updated = pattern.sub(generated, readme)
    else:
        anchor = "## Engineering Activity"
        updated = readme.replace(anchor, generated + "\n\n" + anchor, 1)
    readme_path.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    main()
