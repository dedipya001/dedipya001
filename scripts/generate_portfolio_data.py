import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.github.com"
USERNAME = "dedipya001"
FEATURED = {
    "AI-Relocation-Assistant",
    "The-One-Interview",
    "Trash-Trace",
    "Skin-type-detection",
    "3D-CNN-Vs-CNN-RNN-in-Video-Recognition",
    "Face-Recognition-Analysis-Comparison",
}


def request_json(url: str) -> object:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "dedipya-portfolio-generator",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())


def main() -> None:
    repositories = request_json(
        f"{API}/users/{USERNAME}/repos?per_page=100&sort=updated&direction=desc"
    )
    selected = []
    for repo in repositories:
        if repo["name"] not in FEATURED:
            continue
        selected.append(
            {
                "name": repo["name"].replace("-", " "),
                "description": repo.get("description") or "Engineering project and technical exploration.",
                "url": repo["html_url"],
                "language": repo.get("language") or "Multi-stack",
                "topics": repo.get("topics", []),
                "updated_at": repo["updated_at"],
                "stars": repo["stargazers_count"],
            }
        )
    selected.sort(key=lambda item: item["updated_at"], reverse=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "projects": selected,
    }
    output = Path("docs/data/projects.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
