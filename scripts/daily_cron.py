#!/usr/bin/env python3
"""Daily cron script — pre-fetches today's Wikipedia puzzle.

Usage:
    python scripts/daily_cron.py            # fetch today
    python scripts/daily_cron.py --force    # re-fetch even if file already exists

Run this daily (e.g. via crontab or a scheduler):
    0 2 * * * /path/to/venv/bin/python /path/to/scripts/daily_cron.py

Puzzles are saved to:
    backend/daily_puzzles/YYYY-MM-DD.json
"""

import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Hardcoded article list — edit this to your taste.
# Articles are selected deterministically: index = date.toordinal() % len(ARTICLES)
# ---------------------------------------------------------------------------
ARTICLES: list[str] = [
    # --- Add your French Wikipedia article titles here ---
    "Paris",
    "Locomotive à vapeur",
    # "Tour Eiffel",
    # "Révolution française",
    # "Napoléon Bonaparte",
    # "Victor Hugo",
    # "Versailles",
    # "Mont Blanc",
    # "Impressionnisme",
    # "Citroën",
]

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
_BACKEND_DIR = _PROJECT_ROOT / "backend"
_DAILY_DIR = _BACKEND_DIR / "daily_puzzles"


def _pick_article(target_date: date) -> str:
    """Deterministically pick an article for the given date."""
    if not ARTICLES:
        raise ValueError("ARTICLES list is empty — add some Wikipedia titles first.")
    idx = target_date.toordinal() % len(ARTICLES)
    return ARTICLES[idx]


async def fetch_and_save(target_date: date, force: bool = False) -> None:
    # Add backend to sys.path so we can import app modules directly
    sys.path.insert(0, str(_BACKEND_DIR))
    from app.config import MAX_PARAGRAPHS  # noqa: PLC0415
    from app.wiki import fetch_intro  # noqa: PLC0415

    out_path = _DAILY_DIR / f"{target_date.isoformat()}.json"

    if out_path.exists() and not force:
        print(f"[cron] Puzzle for {target_date} already exists ({out_path.name}). "
              "Use --force to overwrite.")
        return

    title = _pick_article(target_date)
    print(f"[cron] Fetching '{title}' for {target_date} …")

    data = await fetch_intro(title, max_paragraphs=MAX_PARAGRAPHS)
    data["date"] = target_date.isoformat()

    _DAILY_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[cron] Saved → {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Pre-fetch today's daily puzzle.")
    parser.add_argument(
        "--date",
        help="Target date in YYYY-MM-DD format (default: today)",
        default=None,
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch and overwrite even if the file already exists.",
    )
    args = parser.parse_args()

    if args.date:
        target = date.fromisoformat(args.date)
    else:
        target = date.today()

    asyncio.run(fetch_and_save(target, force=args.force))


if __name__ == "__main__":
    main()
