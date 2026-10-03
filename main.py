import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

GITHUB_USERNAME = os.environ.get("GITHUB_USERNAME")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

TIMEZONE = ZoneInfo("Asia/Jakarta")


def check_push_today():
    if not GITHUB_USERNAME:
        print("ERROR: GITHUB_USERNAME belum diatur.")
        return None

    if not GITHUB_TOKEN:
        print("ERROR: GITHUB_TOKEN belum diatur.")
        return None

    url = f"https://api.github.com/users/{GITHUB_USERNAME}/events"

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "X-GitHub-Api-Version": "2026-03-10",
    }

    params = {
        "per_page": 100,
    }

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=20,
    )

    if response.status_code != 200:
        print(
            f"ERROR: GitHub API mengembalikan "
            f"HTTP {response.status_code}"
        )
        print(response.text)
        return None

    events = response.json()

    today = datetime.now(TIMEZONE).date()

    for event in events:
        if event.get("type") != "PushEvent":
            continue

        created_at = event.get("created_at")

        if not created_at:
            continue

        event_time = datetime.fromisoformat(
            created_at.replace("Z", "+00:00")
        ).astimezone(TIMEZONE)

        if event_time.date() == today:
            repository = event.get("repo", {}).get(
                "name",
                "unknown repository"
            )

            print(
                f"Push terdeteksi hari ini: {repository}"
            )

            return True

    print("Belum ditemukan PushEvent hari ini.")

    return False


if __name__ == "__main__":
    result = check_push_today()

    # 0 = sudah push
    # 1 = belum push
    # 2 = error

    if result is True:
        sys.exit(0)

    if result is False:
        sys.exit(1)

    sys.exit(2)
