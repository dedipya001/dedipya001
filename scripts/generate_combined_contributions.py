import json
import os
import urllib.request
from datetime import date, timedelta
from pathlib import Path

API_URL = "https://api.github.com/graphql"
QUERY = """
query($username: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $username) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        weeks {
          contributionDays { date contributionCount }
        }
      }
    }
  }
}
"""


def fetch(username: str, token: str, start: date, end: date) -> dict[str, int]:
    payload = {
        "query": QUERY,
        "variables": {
            "username": username,
            "from": f"{start.isoformat()}T00:00:00Z",
            "to": f"{end.isoformat()}T23:59:59Z",
        },
    }
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "combined-contribution-graph",
        },
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        result = json.loads(response.read())
    if result.get("errors"):
        raise RuntimeError(result["errors"])
    user = result.get("data", {}).get("user")
    if not user:
        raise RuntimeError(f"GitHub user not found: {username}")
    days = user["contributionsCollection"]["contributionCalendar"]["weeks"]
    return {
        day["date"]: day["contributionCount"]
        for week in days
        for day in week["contributionDays"]
    }


def level(count: int, maximum: int) -> int:
    if count == 0:
        return 0
    ratio = count / max(maximum, 1)
    if ratio <= 0.15:
        return 1
    if ratio <= 0.35:
        return 2
    if ratio <= 0.65:
        return 3
    return 4


def render(values: dict[str, int], start: date, end: date) -> str:
    colors = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
    cell, gap, left, top = 11, 3, 34, 44
    first_sunday = start - timedelta(days=(start.weekday() + 1) % 7)
    weeks = ((end - first_sunday).days // 7) + 1
    width, height = left + weeks * (cell + gap) + 20, 172
    maximum = max(values.values(), default=1)
    total = sum(values.values())

    cells = []
    month_labels = []
    last_month = None
    current = first_sunday
    while current <= end:
        week = (current - first_sunday).days // 7
        weekday = (current.weekday() + 1) % 7
        count = values.get(current.isoformat(), 0)
        x = left + week * (cell + gap)
        y = top + weekday * (cell + gap)
        cells.append(
            f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" '
            f'fill="{colors[level(count, maximum)]}"><title>{current}: {count} contributions</title></rect>'
        )
        if current.day <= 7 and current.month != last_month:
            month_labels.append(f'<text x="{x}" y="32" class="label">{current:%b}</text>')
            last_month = current.month
        current += timedelta(days=1)

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Combined GitHub contribution graph">
<style>.title{{font:600 14px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#c9d1d9}}.label{{font:10px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#8b949e}}</style>
<rect width="100%" height="100%" rx="8" fill="#0d1117"/>
<text x="16" y="20" class="title">{total} combined contributions in the last year</text>
{''.join(month_labels)}
<text x="5" y="67" class="label">Mon</text><text x="5" y="95" class="label">Wed</text><text x="5" y="123" class="label">Fri</text>
{''.join(cells)}
</svg>'''


def main() -> None:
    end = date.today()
    start = end - timedelta(days=364)
    accounts = [
        (os.environ["PERSONAL_GITHUB_USERNAME"], os.environ["PERSONAL_GITHUB_TOKEN"]),
        (os.environ["WORK_GITHUB_USERNAME"], os.environ["WORK_GITHUB_TOKEN"]),
    ]
    merged: dict[str, int] = {}
    for username, token in accounts:
        for day, count in fetch(username, token, start, end).items():
            merged[day] = merged.get(day, 0) + count
    output = Path("assets/combined-contributions.svg")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(merged, start, end), encoding="utf-8")


if __name__ == "__main__":
    main()
