"""Regenerate data/catalog.json from the upstream public-apis README.

Usage:
    python tools/build_snapshot.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qtapis.store import catalog_from_markdown, fetch_markdown, save_snapshot


def main() -> int:
    print("Fetching README from public-apis/public-apis ...")
    markdown = fetch_markdown()
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    catalog = catalog_from_markdown(markdown, fetched_at=stamp)
    path = save_snapshot(catalog)

    counts = catalog.counts()
    print(f"Parsed {len(catalog.records)} APIs across {len(counts)} categories")
    for name in sorted(counts, key=str.lower):
        print(f"  {counts[name]:>4}  {name}")
    print(f"\nWrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())