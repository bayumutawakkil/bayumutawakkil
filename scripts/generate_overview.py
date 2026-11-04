#!/usr/bin/env python3
"""Generate a dark, GitHub-style single-card SVG of public GitHub profile statistics."""
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

# GitHub dark-dimmed inspired palette.
BG = "#0d1117"          # GitHub canvas default
PANEL = "#161b22"       # GitHub canvas subtle
CARD = "#21262d"        # elevated surface
BORDER = "#30363d"      # GitHub border default
TEXT = "#e6edf3"        # primary text
MUTED = "#8b949e"       # secondary text
ACCENT = "#58a6ff"      # GitHub link blue
ACCENT_2 = "#3fb950"    # GitHub success green
ACCENT_3 = "#d2a8ff"    # soft purple
TRACK = "#30363d"
OTHER = "#6e7681"

LANGUAGE_COLORS = {
    "Python": "#3572A5", "TypeScript": "#3178C6", "JavaScript": "#f1e05a",
    "Dart": "#00B4AB", "Java": "#b07219", "PHP": "#4F5D95",
    "C": "#555555", "C++": "#f34b7d", "C#": "#178600", "Go": "#00ADD8",
    "Rust": "#dea584", "HTML": "#e34c26", "CSS": "#563d7c",
    "Kotlin": "#A97BFF", "Ruby": "#701516", "Shell": "#89e051",
    "Jupyter Notebook": "#DA5B0B", "Vue": "#41b883", "Svelte": "#ff3e00",
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


FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"


def text(x: float, y: float, value: str, *, size: int = 14, color: str = TEXT,
         weight: int = 400, anchor: str = "start", mono: bool = False) -> str:
    family = MONO if mono else FONT
    return (f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" '
            f'font-weight="{weight}" text-anchor="{anchor}" font-family="{family}">'
            f'{escape(str(value))}</text>')


def render_svg(user: dict[str, Any], repositories: list[dict[str, Any]],
               language_totals: dict[str, int]) -> str:
    width, height = 1100, 560
    owned = [r for r in repositories if not r.get("fork", False) and not r.get("archived", False)]
    metrics = [
        ("Repositories", fmt_number(int(user.get("public_repos", len(owned)))), ACCENT),
        ("Stars earned", fmt_number(sum(int(r.get("stargazers_count", 0)) for r in owned)), "#e3b341"),
        ("Forks received", fmt_number(sum(int(r.get("forks_count", 0)) for r in owned)), ACCENT_2),
        ("Followers", fmt_number(int(user.get("followers", 0))), ACCENT_3),
    ]
    total_bytes = sum(language_totals.values())
    sorted_languages = sorted(language_totals.items(), key=lambda item: item[1], reverse=True)
    top = sorted_languages[:TOP_LANGUAGES]
    other_bytes = sum(value for _, value in sorted_languages[TOP_LANGUAGES:])

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">GitHub profile statistics</title>',
        '<desc id="desc">Public repositories, stars, forks, followers, and programming language distribution.</desc>',
        '<defs>',
        f'  <linearGradient id="hdr" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0%" stop-color="{ACCENT}" stop-opacity="0.9"/>'
        f'<stop offset="100%" stop-color="{ACCENT_3}" stop-opacity="0.9"/></linearGradient>',
        f'  <radialGradient id="glow" cx="0.9" cy="0.0" r="0.6">'
        f'<stop offset="0%" stop-color="{ACCENT}" stop-opacity="0.18"/>'
        f'<stop offset="100%" stop-color="{ACCENT}" stop-opacity="0"/></radialGradient>',
        '</defs>',
        f'<rect width="{width}" height="{height}" rx="12" fill="{BG}"/>',
        f'<rect width="{width}" height="{height}" rx="12" fill="url(#glow)"/>',
        f'<rect x="0.5" y="0.5" width="{width-1}" height="{height-1}" rx="12" fill="none" stroke="{BORDER}"/>',
        # Header
        f'<rect x="40" y="36" width="1020" height="3" rx="1.5" fill="url(#hdr)"/>',
        text(40, 78, "Profile overview", size=24, color=TEXT, weight=600),
        text(40, 100, "Public GitHub activity and language breakdown", size=13, color=MUTED),
        text(1060, 78, f"@{USERNAME}", size=14, color=ACCENT, weight=600, anchor="end", mono=True),
    ]

    # Metric tiles
    tile_w, gap = 240, 20
    for index, (label, value, color) in enumerate(metrics):
        x = 40 + index * (tile_w + gap)
        parts.extend([
            f'<rect x="{x}" y="128" width="{tile_w}" height="104" rx="10" fill="{PANEL}" stroke="{BORDER}"/>',
            f'<circle cx="{x+22}" cy="156" r="4" fill="{color}"/>',
            text(x + 36, 161, label.upper(), size=11, color=MUTED, weight=600),
            text(x + 22, 210, value, size=32, color=TEXT, weight=600),
        ])

    # Language panel
    parts.extend([
        f'<rect x="40" y="256" width="1020" height="264" rx="10" fill="{PANEL}" stroke="{BORDER}"/>',
        text(64, 290, "Language distribution", size=15, color=TEXT, weight=600),
        text(1036, 290, "by code bytes", size=11, color=MUTED, anchor="end", mono=True),
    ])

    if not top or total_bytes <= 0:
        parts.append(text(64, 330, "No language data available", size=14, color=MUTED))
    else:
        bar_x, bar_y, bar_w, bar_h = 64, 310, 972, 12
        # Clip the stacked bar to rounded ends.
        parts.append(
            f'<clipPath id="barclip"><rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="6"/></clipPath>'
        )
        parts.append(f'<g clip-path="url(#barclip)">')
        cursor = bar_x
        segments = [(name, amount, LANGUAGE_COLORS.get(name, "#8b949e")) for name, amount in top]
        if other_bytes:
            segments.append(("Other", other_bytes, OTHER))
        for name, amount, color in segments:
            seg_w = bar_w * amount / total_bytes
            if seg_w > 0:
                parts.append(f'<rect x="{cursor:.2f}" y="{bar_y}" width="{seg_w:.2f}" height="{bar_h}" fill="{color}"/>')
                cursor += seg_w
        parts.append('</g>')

        # Two-column legend
        col_xs = [64, 580]
        for i, (language, amount) in enumerate(top):
            col = 0 if i < 3 else 1
            row = i if i < 3 else i - 3
            x = col_xs[col]
            y = 362 + row * 44
            pct = amount / total_bytes * 100
            color = LANGUAGE_COLORS.get(language, "#8b949e")
            parts.extend([
                f'<circle cx="{x+6}" cy="{y-5}" r="6" fill="{color}"/>',
                text(x + 22, y, language, size=14, color=TEXT, weight=500),
                f'<rect x="{x+200}" y="{y-12}" width="260" height="8" rx="4" fill="{TRACK}"/>',
                f'<rect x="{x+200}" y="{y-12}" width="{260*pct/100:.2f}" height="8" rx="4" fill="{color}"/>',
                text(x + 480, y, f"{pct:.1f}%", size=13, color=MUTED, weight=500, anchor="end", mono=True),
            ])

    parts.append(
        text(40, 546, "Generated from public GitHub data", size=11, color=MUTED)
    )
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