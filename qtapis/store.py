"""Catalog loading: bundled snapshot on disk, with refresh from GitHub."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

from .catalog import RAW_README_URL, Catalog, ApiRecord, parse_readme
from .paths import data_file, writable_data_path

# Read: the copy shipped inside the bundle (frozen) or the repo (source).
BUNDLED_SNAPSHOT = data_file("catalog.json")
# Write: a user-writable location, since a onefile bundle extracts read-only.
SNAPSHOT_PATH = writable_data_path() / "catalog.json"

USER_AGENT = "QtPublicAPIsExplorer/2.4 (+https://github.com/public-apis/public-apis)"


class CatalogError(RuntimeError):
    """Raised when the catalog cannot be loaded from any source."""


def fetch_markdown(timeout: int = 20) -> str:
    """Download the raw README from the public-apis repository."""
    req = urllib.request.Request(RAW_README_URL, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")
    except urllib.error.URLError as exc:
        raise CatalogError(f"Could not reach GitHub: {exc.reason}") from exc
    except OSError as exc:
        raise CatalogError(f"Network error: {exc}") from exc


def catalog_from_markdown(markdown: str, fetched_at: str = "") -> Catalog:
    records = parse_readme(markdown)
    if not records:
        raise CatalogError("No API records found in the upstream README.")
    return Catalog(records=records, fetched_at=fetched_at)


def save_snapshot(catalog: Catalog, path: Path | None = None) -> Path:
    path = Path(path) if path is not None else SNAPSHOT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": catalog.fetched_at,
        "count": len(catalog.records),
        "records": [r.to_dict() for r in catalog.records],
    }
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    return path


def load_snapshot() -> Catalog | None:
    """Load the user's cache if present, else the bundled snapshot.

    Returns None when neither exists or both are unreadable.
    """
    for path in (SNAPSHOT_PATH, BUNDLED_SNAPSHOT):
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            records = [ApiRecord.from_dict(d) for d in payload.get("records", [])]
        except (json.JSONDecodeError, OSError, TypeError):
            continue
        if records:
            return Catalog(records=records, fetched_at=payload.get("fetched_at", ""))
    return None


def load_catalog(prefer_network: bool = False) -> Catalog:
    """Return a catalog, preferring the bundled snapshot for offline-first startup."""
    if prefer_network:
        try:
            return catalog_from_markdown(fetch_markdown())
        except CatalogError:
            pass
    catalog = load_snapshot()
    if catalog is None:
        # No snapshot: we must go to the network.
        return catalog_from_markdown(fetch_markdown())
    return catalog