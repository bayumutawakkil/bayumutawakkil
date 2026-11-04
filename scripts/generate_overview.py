#!/usr/bin/env python3
"""Generate a single SVG combining public GitHub stats and language usage."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape


API_ROOT = "https://api.github.com"
USERNAME = os.getenv("GITHUB_USERNAME", "bayumutawakkil").strip()
TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
MAX_REPOS = max(1, int(os.getenv("MAX_REPOS_FOR_LANGUAGES", "100")))
TOP_LANGUAGES = max(1, min(10, int(os.getenv("TOP_LANGUAGES", "6"))))
OUTPUT_FILE = Path(os.getenv("OUTPUT_FILE", "assets/github-overview.svg"))

BG = "#0D1117"
PANEL = "#111820"
BORDER = "#263442"
CYAN = "#00D4FF"
TEXT = "#C9D1D9"
MUTED = "#8B949E"
TRACK = "#263442"

LANGUAGE_COLORS = {
    "Python": "#3572A5",
    "TypeScript": "#3178C6",
    "JavaScript": "#F1E05A",
    "Dart": "#00B4AB",
    "Java": "#B07219",
    "PHP": "#4F5D95",
    "C": "#555555",
    "C++": "#F34B7D",
    "C#": "#178600",
    "Go": "#00ADD8",
    "Rust": "#DEA584",
    "HTML": "#E34C26",
    "CSS": "#563D7C",
    "Kotlin": "#A97BFF",
    "Ruby": "#701516",
    "Shell": "#89E051",
    "Jupyter Notebook": "#DA5B0B",
    "Vue": "#41B883",
    "Svelte": "#FF3E00",
}


def api_get(path: str) -> Any:
    """GET a GitHub REST API path and decode its JSON response."""
    url = path if path.startswith("https://") else f"{API_ROOT}{path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "github-overview-svg-generator",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GitHub API request failed ({exc.code}) for {url}: {detail[:500]}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error requesting {url}: {exc}") from exc


def get_owned_repositories() -> list[dict[str, Any]]:
    """Fetch all non-fork, non-archived repositories owned by the account."""
    repositories: list[dict[str, Any]] = []
    page = 1

    while True:
        query = urllib.parse.urlencode({
            "type": "owner",
            "sort": "updated",
            "direction": "desc",
            "per_page": 100,
            "page": page,
        })
        batch = api_get(f"/users/{urllib.parse.quote(USERNAME)}/repos?{query}")
        if not isinstance(batch, list) or not batch:
            break

        repositories.extend(
            repo for repo in batch
            if not repo.get("fork", False) and not repo.get("archived", False)
        )

        if len(batch) < 100:
            break
        page += 1

    return repositories


def get_language_bytes(repo: dict[str, Any]) -> dict[str, int]:
    """Fetch language byte counts for one repository."""
    full_name = repo.get("full_name")
    if not full_name:
        return {}
    encoded_name = urllib.parse.quote(full_name, safe="/")
    try:
        data = api_get(f"/repos/{encoded_name}/languages")
        return {
            str(language): int(byte_count)
            for language, byte_count in data.items()
            if isinstance(byte_count, int) and byte_count > 0
        }
    except Exception as exc:  # Keep a partial card if an individual repo fails.
        print(f"Warning: skipped language data for {full_name}: {exc}", file=sys.stderr)
        return {}


def collect_language_totals(repositories: list[dict[str, Any]]) -> dict[str, int]:
    """Aggregate language byte counts across the configured repository sample."""
    sample = repositories[:MAX_REPOS]
    totals: dict[str, int] = {}

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(get_language_bytes, repo) for repo in sample]
        for future in as_completed(futures):
            for language, byte_count in future.result().items():
                totals[language] = totals.get(language, 0) + byte_count

    return totals


def fmt_number(value: int) -> str:
    return f"{value:,}"


def svg_text(x: int, y: int, value: str, *, size: int = 14,
             color: str = TEXT, weight: int = 400,
             anchor: str = "start", family: str = "Inter,Segoe UI,Arial,sans-serif") -> str:
    return (
        f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" '
        f'font-weight="{weight}" text-anchor="{anchor}" '
        f'font-family="{family}">{escape(str(value))}</text>'
    )


def render_svg(user: dict[str, Any], repositories: list[dict[str, Any]],
               language_totals: dict[str, int]) -> str:
    width, height = 1000, 390
    owned_repos = [
        repo for repo in repositories
        if not repo.get("fork", False) and not repo.get("archived", False)
    ]
    stars = sum(int(repo.get("stargazers_count", 0)) for repo in owned_repos)
    forks = sum(int(repo.get("forks_count", 0)) for repo in owned_repos)
    followers = int(user.get("followers", 0))
    public_repos = int(user.get("public_repos", len(owned_repos)))

    total_bytes = sum(language_totals.values())
    sorted_languages = sorted(language_totals.items(), key=lambda item: item[1], reverse=True)
    top_languages = sorted_languages[:TOP_LANGUAGES]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">GitHub Overview</title>',
        '<desc id="desc">Public GitHub profile statistics and most-used programming languages.</desc>',
        f'<rect width="{width}" height="{height}" rx="18" fill="{BG}"/>',
        f'<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="17" fill="none" stroke="{BORDER}"/>',
        f'<rect x="24" y="24" width="952" height="342" rx="13" fill="{PANEL}" stroke="{BORDER}"/>',
        svg_text(48, 62, "GITHUB OVERVIEW", size=13, color=CYAN, weight=700),
        svg_text(952, 62, f"@{USERNAME}", size=12, color=MUTED, anchor="end"),
        f'<line x1="48" y1="82" x2="952" y2="82" stroke="{BORDER}"/>',
    ]

    # Left column: four compact statistic tiles.
    metrics = [
        ("PUBLIC REPOSITORIES", fmt_number(public_repos)),
        ("STARS EARNED", fmt_number(stars)),
        ("FORKS", fmt_number(forks)),
        ("FOLLOWERS", fmt_number(followers)),
    ]
    positions = [(48, 112), (264, 112), (48, 224), (264, 224)]
    for (label, value), (x, y) in zip(metrics, positions):
        parts.extend([
            f'<rect x="{x}" y="{y}" width="196" height="88" rx="9" fill="{BG}" stroke="{BORDER}"/>',
            svg_text(x + 16, y + 27, label, size=10, color=MUTED, weight=600),
            svg_text(x + 16, y + 64, value, size=27, color=TEXT, weight=700),
            f'<rect x="{x+16}" y="{y+76}" width="34" height="3" rx="1.5" fill="{CYAN}"/>',
        ])

    # Divider and language section.
    parts.extend([
        f'<line x1="488" y1="104" x2="488" y2="338" stroke="{BORDER}"/>',
        svg_text(520, 119, "MOST USED LANGUAGES", size=13, color=CYAN, weight=700),
        svg_text(952, 119, "BY CODE BYTES", size=10, color=MUTED, anchor="end"),
    ])

    if not top_languages or total_bytes == 0:
        parts.append(svg_text(520, 170, "No language data available yet.", size=13, color=MUTED))
    else:
        bar_x, bar_y, bar_width, bar_height = 520, 143, 432, 10
        cursor = bar_x
        for language, byte_count in top_languages:
            segment_width = bar_width * byte_count / total_bytes
            if segment_width > 0.5:
                color = LANGUAGE_COLORS.get(language, "#6E7681")
                parts.append(
                    f'<rect x="{cursor:.2f}" y="{bar_y}" width="{segment_width:.2f}" '
                    f'height="{bar_height}" fill="{color}"/>'
                )
                cursor += segment_width

        row_start = 188
        row_gap = 27
        for index, (language, byte_count) in enumerate(top_languages):
            y = row_start + index * row_gap
            percentage = (byte_count / total_bytes) * 100
            color = LANGUAGE_COLORS.get(language, "#6E7681")
            parts.extend([
                f'<circle cx="527" cy="{y-4}" r="4" fill="{color}"/>',
                svg_text(541, y, language, size=12, color=TEXT, weight=500),
                svg_text(952, y, f"{percentage:.1f}%", size=12, color=MUTED, anchor="end"),
            ])

    parts.extend([
        f'<line x1="48" y1="338" x2="952" y2="338" stroke="{BORDER}"/>',
        svg_text(48, 356, "Public repositories · Forks and archived repositories excluded from stars/languages", size=9, color=MUTED),
        svg_text(952, 356, f"Updated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", size=9, color=MUTED, anchor="end"),
        "</svg>",
    ])
    return "\n".join(parts)


def main() -> None:
    if not USERNAME:
        raise SystemExit("GITHUB_USERNAME must not be empty.")

    print(f"Fetching public profile for {USERNAME}...")
    user = api_get(f"/users/{urllib.parse.quote(USERNAME)}")
    repositories = get_owned_repositories()
    print(f"Found {len(repositories)} owned, non-fork, non-archived repositories.")

    language_totals = collect_language_totals(repositories)
    print(f"Collected language data for up to {min(len(repositories), MAX_REPOS)} repositories.")

    svg = render_svg(user, repositories, language_totals)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(svg, encoding="utf-8")
    print(f"Generated {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
