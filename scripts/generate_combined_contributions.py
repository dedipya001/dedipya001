import json
import os
import urllib.request
from datetime import date, timedelta
from pathlib import Path

API_URL = "https://api.github.com/graphql"
QUERY = """
query($username: String!, $from: DateTime!, $to: DateTime!, $created: String!, $merged: String!, $reviewed: String!, $approved: String!) {
  user(login: $username) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
  created: search(type: ISSUE, query: $created) { issueCount }
  merged: search(type: ISSUE, query: $merged) { issueCount }
  reviewed: search(type: ISSUE, query: $reviewed) { issueCount }
  approved: search(type: ISSUE, query: $approved) { issueCount }
}
"""


def graphql(username: str, token: str, start: date, end: date) -> tuple[dict[str, int], dict[str, int]]:
    since = start.isoformat()
    variables = {
        "username": username,
        "from": f"{start.isoformat()}T00:00:00Z",
        "to": f"{end.isoformat()}T23:59:59Z",
        "created": f"is:pr author:{username} created:>={since}",
        "merged": f"is:pr author:{username} is:merged merged:>={since}",
        "reviewed": f"is:pr reviewed-by:{username} updated:>={since}",
        "approved": f"is:pr reviewed-by:{username} review:approved updated:>={since}",
    }
    request = urllib.request.Request(
        API_URL,
        data=json.dumps({"query": QUERY, "variables": variables}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "dedipya-engineering-dashboard",
        },
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        result = json.loads(response.read())
    if result.get("errors"):
        raise RuntimeError(json.dumps(result["errors"], indent=2))
    data = result["data"]
    if not data.get("user"):
        raise RuntimeError(f"GitHub user not found: {username}")
    weeks = data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    days = {
        item["date"]: item["contributionCount"]
        for week in weeks
        for item in week["contributionDays"]
    }
    metrics = {key: data[key]["issueCount"] for key in ("created", "merged", "reviewed", "approved")}
    return days, metrics


def contribution_level(count: int, maximum: int) -> int:
    if count == 0:
        return 0
    ratio = count / max(maximum, 1)
    return 1 if ratio <= 0.15 else 2 if ratio <= 0.35 else 3 if ratio <= 0.65 else 4


def streaks(values: dict[str, int], end: date) -> tuple[int, int]:
    ordered = sorted((date.fromisoformat(day), count) for day, count in values.items())
    longest = running = 0
    for _, count in ordered:
        running = running + 1 if count else 0
        longest = max(longest, running)
    current = 0
    day = end
    while values.get(day.isoformat(), 0) > 0:
        current += 1
        day -= timedelta(days=1)
    return current, longest


def render(values: dict[str, int], metrics: dict[str, int], start: date, end: date) -> str:
    colors = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
    cell, gap, left, top = 11, 3, 34, 132
    first_sunday = start - timedelta(days=(start.weekday() + 1) % 7)
    weeks = ((end - first_sunday).days // 7) + 1
    width, height = left + weeks * (cell + gap) + 22, 268
    maximum = max(values.values(), default=1)
    total = sum(values.values())
    active_days = sum(1 for count in values.values() if count)
    current_streak, longest_streak = streaks(values, end)

    cards = [
        ("Contributions", total),
        ("Active days", active_days),
        ("Current streak", current_streak),
        ("Longest streak", longest_streak),
        ("PRs created", metrics["created"]),
        ("PRs merged", metrics["merged"]),
        ("PRs reviewed", metrics["reviewed"]),
        ("PRs approved", metrics["approved"]),
    ]
    card_markup = []
    card_width = (width - 46) / 4
    for index, (label, value) in enumerate(cards):
        row, column = divmod(index, 4)
        x = 16 + column * (card_width + 5)
        y = 42 + row * 40
        card_markup.append(
            f'<rect x="{x}" y="{y}" width="{card_width}" height="34" rx="7" fill="#161b22" stroke="#30363d"/>'
            f'<text x="{x + 10}" y="{y + 14}" class="metric-label">{label}</text>'
            f'<text x="{x + 10}" y="{y + 29}" class="metric-value">{value}</text>'
        )

    cells, months = [], []
    last_month = None
    current = first_sunday
    while current <= end:
        week = (current - first_sunday).days // 7
        weekday = (current.weekday() + 1) % 7
        count = values.get(current.isoformat(), 0)
        x = left + week * (cell + gap)
        y = top + weekday * (cell + gap)
        cells.append(
            f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{colors[contribution_level(count, maximum)]}">'
            f'<title>{current}: {count} contributions</title></rect>'
        )
        if current.day <= 7 and current.month != last_month:
            months.append(f'<text x="{x}" y="{top - 10}" class="label">{current:%b}</text>')
            last_month = current.month
        current += timedelta(days=1)

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Combined engineering activity dashboard">
<style>
.title{{font:700 17px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#f0f6fc}}
.subtitle{{font:11px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#8b949e}}
.label,.metric-label{{font:10px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#8b949e}}
.metric-value{{font:700 14px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#58a6ff}}
</style>
<rect width="100%" height="100%" rx="12" fill="#0d1117" stroke="#30363d"/>
<text x="16" y="23" class="title">Combined Engineering Activity</text>
<text x="16" y="37" class="subtitle">Personal projects, professional delivery and proof-of-concept work · rolling 12 months</text>
{''.join(card_markup)}
{''.join(months)}
<text x="5" y="{top + 23}" class="label">Mon</text><text x="5" y="{top + 51}" class="label">Wed</text><text x="5" y="{top + 79}" class="label">Fri</text>
{''.join(cells)}
<text x="16" y="252" class="subtitle">Activity is aggregated from two authenticated GitHub identities. Private repository names and confidential content are never exposed.</text>
</svg>'''


def main() -> None:
    end = date.today()
    start = end - timedelta(days=364)
    accounts = [
        (os.environ["PERSONAL_GITHUB_USERNAME"], os.environ["PERSONAL_GITHUB_TOKEN"]),
        (os.environ["WORK_GITHUB_USERNAME"], os.environ["WORK_GITHUB_TOKEN"]),
    ]
    merged: dict[str, int] = {}
    totals = {"created": 0, "merged": 0, "reviewed": 0, "approved": 0}
    for username, token in accounts:
        values, metrics = graphql(username, token, start, end)
        for day, count in values.items():
            merged[day] = merged.get(day, 0) + count
        for key, count in metrics.items():
            totals[key] += count
    output = Path("assets/combined-engineering-activity.svg")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(merged, totals, start, end), encoding="utf-8")


if __name__ == "__main__":
    main()
