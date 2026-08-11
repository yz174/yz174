"""Scrape the public GitHub contributions calendar - no token required.

    python scripts/fetch_contributions.py            # username from data/profile.json
    python scripts/fetch_contributions.py octocat

Writes data/contributions.json: the raw days plus derived stats (streaks, best
day, monthly totals).
"""

import argparse
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "data" / "profile.json"
OUT = ROOT / "data" / "contributions.json"

URL = "https://github.com/users/{user}/contributions"
UA = "Mozilla/5.0 (compatible; profile-art/1.0; +https://github.com/{user})"
COUNT_RE = re.compile(r"^\s*(\d[\d,]*)\s+contribution")


def scrape(user: str) -> list[dict]:
    r = requests.get(
        URL.format(user=user),
        headers={"User-Agent": UA.format(user=user), "X-Requested-With": "XMLHttpRequest"},
        timeout=30,
    )
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    cells = soup.select("td.ContributionCalendar-day[data-date]") or soup.select(
        "rect[data-date]"
    )
    if not cells:
        raise SystemExit(f"no contribution cells found for {user!r} - is the profile public?")

    # Counts live in sibling <tool-tip for="..."> elements on the current markup.
    tips = {}
    for tip in soup.find_all("tool-tip"):
        target = tip.get("for")
        if not target:
            continue
        m = COUNT_RE.match(tip.get_text(" ", strip=True))
        tips[target] = int(m.group(1).replace(",", "")) if m else 0

    days = []
    for c in cells:
        raw = c.get("data-count")
        if raw is None:
            raw = tips.get(c.get("id"), 0)
        days.append(
            {
                "date": c["data-date"],
                "count": int(raw),
                "level": int(c.get("data-level", 0)),
            }
        )
    days.sort(key=lambda d: d["date"])
    return days


def stats(days: list[dict]) -> dict:
    counts = [(date.fromisoformat(d["date"]), d["count"]) for d in days]
    today = datetime.now(timezone.utc).date()

    longest = run = 0
    for _, c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)

    tail = counts[:]
    if tail and tail[-1][0] == today and tail[-1][1] == 0:
        tail.pop()  # today is still in progress
    current = 0
    for _, c in reversed(tail):
        if not c:
            break
        current += 1

    monthly: dict[str, int] = {}
    for d, c in counts:
        monthly[d.strftime("%Y-%m")] = monthly.get(d.strftime("%Y-%m"), 0) + c

    best = max(counts, key=lambda x: x[1]) if counts else (today, 0)
    return {
        "total": sum(c for _, c in counts),
        "active_days": sum(1 for _, c in counts if c),
        "current_streak": current,
        "longest_streak": longest,
        "best_day": {"date": best[0].isoformat(), "count": best[1]},
        "monthly": [{"month": m, "total": t} for m, t in sorted(monthly.items())],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("username", nargs="?")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    user = args.username or json.loads(CFG.read_text(encoding="utf-8"))["username"]
    days = scrape(user)
    payload = {
        "username": user,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "from": days[0]["date"],
        "to": days[-1]["date"],
        "days": days,
        "stats": stats(days),
    }
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {args.out} - {len(days)} days, {payload['stats']['total']} contributions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
