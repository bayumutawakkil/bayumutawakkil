#!/usr/bin/env python3
"""Write the languages used across all owned repos into README.md between SKILL_ICONS markers."""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

API_ROOT = "https://api.github.com"
USERNAME = os.getenv("GITHUB_USERNAME", "bayumutawakkil").strip()
TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
README = Path(os.getenv("README_FILE", "README.md"))
START = "<!-- SKILL_ICONS_START -->"
END = "<!-- SKILL_ICONS_END -->"

# GitHub language name -> Simple Icons slug (what emrocode/skill-icons expects).
# Languages not listed here are skipped and reported in the log.
SLUGS = {
    "Python": "python",
    "TypeScript": "typescript",
    "JavaScript": "javascript",
    "Dart": "dart",
    "Java": "openjdk",
    "HTML": "html5",
    "CSS": "css",
    "Jupyter Notebook": "jupyter",
    "Shell": "gnubash",
    "C": "c",
    "C++": "cplusplus",
    "C#": "csharp",
    "Go": "go",
    "Rust": "rust",
    "Kotlin": "kotlin",
    "Swift": "swift",
    "Ruby": "ruby",
    "PHP": "php",
    "Vue": "vuedotjs",
    "Svelte": "svelte",
    "Dockerfile": "docker",
    "Lua": "lua",
    "Scala": "scala",
    "R": "r",
}


def api_get(path: str) -> Any:
    url = path if path.startswith("https://") else f"{API_ROOT}{path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "tech-stack-readme-updater",
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
        return {str(k): int(v) for k, v in data.items() if isinstance(v, int) and v > 0}
    except Exception as exc:
        print(f"Warning: skipped {full_name}: {exc}", file=sys.stderr)
        return {}


def collect_language_totals(repositories: list[dict[str, Any]]) -> dict[str, int]:
    totals: dict[str, int] = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(get_language_bytes, repo) for repo in repositories]
        for future in as_completed(futures):
            for language, byte_count in future.result().items():
                totals[language] = totals.get(language, 0) + byte_count
    return totals


def build_slug_list(totals: dict[str, int]) -> str:
    slugs: list[str] = []
    for language, _ in sorted(totals.items(), key=lambda item: item[1], reverse=True):
        slug = SLUGS.get(language)
        if slug is None:
            print(f"Skipping unmapped language: {language}")
            continue
        if slug not in slugs:
            slugs.append(slug)
    return ",".join(slugs)


def main() -> None:
    if not USERNAME:
        raise SystemExit("GITHUB_USERNAME must not be empty.")
    repositories = get_owned_repositories()
    print(f"Found {len(repositories)} owned, non-fork, non-archived repositories.")
    totals = collect_language_totals(repositories)
    slug_list = build_slug_list(totals)
    if not slug_list:
        raise SystemExit("No mappable languages found; README left unchanged.")
    print(f"Languages: {slug_list}")

    text = README.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    if not pattern.search(text):
        raise SystemExit(f"Markers {START} / {END} not found in {README}.")
    updated = pattern.sub(f"{START}\n{slug_list}\n{END}", text, count=1)
    README.write_text(updated, encoding="utf-8")
    print(f"Updated {README}")


if __name__ == "__main__":
    main()