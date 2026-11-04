#!/usr/bin/env python3
"""Generate a clean, single-card SVG of public GitHub profile statistics."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

API_ROOT = "https://api.github.com"
USERNAME = os.getenv("GITHUB_USERNAME", "bayumutawakkil").strip()
TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
MAX_REPOS = max(1, int(os.getenv("MAX_REPOS_FOR_LANGUAGES", "100")))
TOP_LANGUAGES = max(1, min(6, int(os.getenv("TOP_LANGUAGES", "6"))))
OUTPUT_FILE = Path(os.getenv("OUTPUT_FILE", "assets/github-overview.svg"))

# Neutral dark UI with restrained cyan/blue accents.
BG = "#0B1220"
PANEL = "#111C2E"
CARD = "#152238"
BORDER = "#263750"
TEXT = "#F1F5F9"
MUTED = "#91A4BC"
ACCENT = "#38BDF8"
TRACK = "#263750"
OTHER = "#64748B"

LANGUAGE_COLORS = {
    "Python": "#3572A5", "TypeScript": "#3178C6", "JavaScript": "#F1E05A",
    "Dart": "#00B4AB", "Java": "#B07219", "PHP": "#4F5D95",
    "C": "#64748B", "C++": "#F34B7D", "C#": "#178600", "Go": "#00ADD8",
    "Rust": "#DEA584", "HTML": "#E34C26", "CSS": "#563D7C",
    "Kotlin": "#A97BFF", "Ruby": "#701516", "Shell": "#89E051",
    "Jupyter Notebook": "#DA5B0B", "Vue": "#41B883", "Svelte": "#FF3E00",
}


def api_get(path: str) -> Any:
    url = path if path.startswith("https://") else f"{API_ROOT}{path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "github-profile-stats-svg",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API request failed ({exc.code}) for {url}: {detail[:400]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error requesting {url}: {exc}") from exc


def get_owned_repositories() -> list[dict[str, Any]]:
    repositories: list[dict[str, Any]] = []
    page = 1
    while True:
        query = urllib.parse.urlencode({
            "type": "owner", "sort": "updated", "direction": "desc",
            "per_page": 100, "page": page,
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
    full_name = repo.get("full_name")
    if not full_name:
        return {}
    try:
        data = api_get(f"/repos/{urllib.parse.quote(full_name, safe='/')}/languages")
        return {
            str(language): int(byte_count)
            for language, byte_count in data.items()
            if isinstance(byte_count, int) and byte_count > 0
        }
    except Exception as exc:
        print(f"Warning: skipped language data for {full_name}: {exc}", file=sys.stderr)
        return {}


def collect_language_totals(repositories: list[dict[str, Any]]) -> dict[str, int]:
    totals: dict[str, int] = {}
    sample = repositories[:MAX_REPOS]
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(get_language_bytes, repo) for repo in sample]
        for future in as_completed(futures):
            for language, byte_count in future.result().items():
                totals[language] = totals.get(language, 0) + byte_count
    return totals


def fmt_number(value: int) -> str:
    return f"{value:,}"


def text(x: float, y: float, value: str, *, size: int = 14,
         color: str = TEXT, weight: int = 400, anchor: str = "start") -> str:
    return (f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" '
            f'font-weight="{weight}" text-anchor="{anchor}" '
            f'font-family="Inter, ui-sans-serif, Segoe UI, Arial, sans-serif">'
            f'{escape(str(value))}</text>')


def render_svg(user: dict[str, Any], repositories: list[dict[str, Any]],
               language_totals: dict[str, int]) -> str:
    width, height = 1000, 450
    owned = [r for r in repositories if not r.get("fork", False) and not r.get("archived", False)]
    metrics = [
        ("PUBLIC REPOSITORIES", fmt_number(int(user.get("public_repos", len(owned)))), "repo"),
        ("STARS EARNED", fmt_number(sum(int(r.get("stargazers_count", 0)) for r in owned)), "star"),
        ("FORKS RECEIVED", fmt_number(sum(int(r.get("forks_count", 0)) for r in owned)), "fork"),
        ("FOLLOWERS", fmt_number(int(user.get("followers", 0))), "people"),
    ]
    total_bytes = sum(language_totals.values())
    sorted_languages = sorted(language_totals.items(), key=lambda item: item[1], reverse=True)
    top = sorted_languages[:TOP_LANGUAGES]
    other_bytes = sum(value for _, value in sorted_languages[TOP_LANGUAGES:])

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">GitHub profile statistics</title>',
        '<desc id="desc">Public repositories, stars, forks, followers, and programming language distribution.</desc>',
        '<defs><linearGradient id="bgGlow" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#12233A"/><stop offset="100%" stop-color="#0B1220"/></linearGradient>',
        '<linearGradient id="accentLine" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#38BDF8"/><stop offset="100%" stop-color="#818CF8"/></linearGradient></defs>',
        f'<rect width="{width}" height="{height}" rx="22" fill="url(#bgGlow)"/>',
        f'<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="21" fill="none" stroke="{BORDER}"/>',
        '<circle cx="930" cy="34" r="100" fill="#1D4ED8" opacity="0.07"/>',
        '<circle cx="930" cy="34" r="62" fill="#38BDF8" opacity="0.035"/>',
        text(42, 52, "GITHUB STATISTICS", size=13, color=ACCENT, weight=750),
        text(42, 77, "Profile overview", size=22, color=TEXT, weight=700),
        '<rect x="42" y="91" width="916" height="2" rx="1" fill="url(#accentLine)" opacity="0.75"/>',
    ]

    # Four metric cards, evenly spaced and deliberately free of account branding.
    card_xs = [42, 276, 510, 744]
    for index, ((label, value, kind), x) in enumerate(zip(metrics, card_xs)):
        parts.extend([
            f'<rect x="{x}" y="112" width="214" height="104" rx="13" fill="{CARD}" stroke="{BORDER}"/>',
            f'<rect x="{x}" y="112" width="3" height="104" rx="1.5" fill="url(#accentLine)"/>',
            text(x + 18, 143, label, size=10, color=MUTED, weight=700),
            text(x + 18, 187, value, size=31, color=TEXT, weight=750),
        ])
        # Small abstract mark; decorative only, not a misleading metric icon.
        parts.append(f'<circle cx="{x+185}" cy="137" r="5" fill="{ACCENT}" opacity="0.85"/>')

    parts.extend([
        f'<rect x="42" y="238" width="916" height="178" rx="15" fill="{PANEL}" stroke="{BORDER}"/>',
        text(64, 273, "LANGUAGE DISTRIBUTION", size=12, color=TEXT, weight=750),
        text(936, 273, f"TOP {len(top)}", size=10, color=MUTED, weight=700, anchor="end"),
    ])

    if not top or total_bytes <= 0:
        parts.append(text(64, 326, "No language data available", size=14, color=MUTED))
    else:
        # Stacked bar includes an Other segment so its full length always represents 100%.
        bar_x, bar_y, bar_width, bar_height = 64, 291, 872, 11
        cursor = bar_x
        segments = [(name, amount, LANGUAGE_COLORS.get(name, "#7C8DA5")) for name, amount in top]
        if other_bytes:
            segments.append(("Other", other_bytes, OTHER))
        for name, amount, color in segments:
            segment_width = bar_width * amount / total_bytes
            if segment_width > 0:
                parts.append(f'<rect x="{cursor:.2f}" y="{bar_y}" width="{segment_width:.2f}" height="{bar_height}" fill="{color}"/>')
                cursor += segment_width

        # Two-column list with proportional mini-bars.
        col_xs = [64, 514]
        for i, (language, amount) in enumerate(top):
            col = 0 if i < 3 else 1
            row = i if i < 3 else i - 3
            x = col_xs[col]
            y = 333 + row * 27
            pct = amount / total_bytes * 100
            color = LANGUAGE_COLORS.get(language, "#7C8DA5")
            parts.extend([
                f'<circle cx="{x+5}" cy="{y-4}" r="4" fill="{color}"/>',
                text(x + 18, y, language, size=12, color=TEXT, weight=600),
                f'<rect x="{x+170}" y="{y-10}" width="210" height="5" rx="2.5" fill="{TRACK}"/>',
                f'<rect x="{x+170}" y="{y-10}" width="{210*pct/100:.2f}" height="5" rx="2.5" fill="{color}"/>',
                text(x + 420, y, f"{pct:.1f}%", size=11, color=MUTED, weight=600, anchor="end"),
            ])
    parts.append('</svg>')
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
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(render_svg(user, repositories, language_totals), encoding="utf-8")
    print(f"Generated {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
