"""Parse the public-apis README into structured records.

Upstream format (per category)::

    ### Animals
    API | Description | Auth | HTTPS | CORS
    |:---|:---|:---|:---|:---|
    | [Cat Facts](https://catfact.ninja/) | Random cat facts | No | Yes | Yes |
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict

RAW_README_URL = (
    "https://raw.githubusercontent.com/public-apis/public-apis/master/README.md"
)

# Only the canonical catalog tables use these headers. The README also contains
# promotional tables (APILayer APIs, MCP Servers) with different shapes that we skip.
_EXPECTED_HEADERS = ("api", "description", "auth", "https", "cors")

_LINK_RE = re.compile(r"^\[([^\]]*)\]\(([^)]*)\)\s*$")
_CATEGORY_RE = re.compile(r"^###\s+(.+?)\s*$")
_H2_RE = re.compile(r"^##\s+(.+?)\s*$")


def _cells(line: str) -> list[str]:
    """Split a markdown table row into stripped cells."""
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def _is_separator(cells: list[str]) -> bool:
    """True for a markdown alignment row such as `|:---|:---|`."""
    populated = [c for c in cells if c]
    return len(populated) >= 2 and all(
        re.fullmatch(r":?-{2,}:?", c) for c in populated
    )


def normalize_auth(raw: str) -> str:
    """Map README auth cells onto a small closed set of display tokens."""
    v = raw.strip().strip("`").lower()
    if not v or v in {"no", "none", "n/a", "-"}:
        return "none"
    if "oauth" in v:
        return "oauth"
    if "api-key" in v or "apikey" in v or "api key" in v:
        return "apikey"
    return v


def normalize_flag(raw: str) -> str:
    """Map README HTTPS/CORS cells onto 'yes' / 'no' / 'unknown'."""
    v = raw.strip().strip("`").lower()
    if v in {"yes", "true", "y"}:
        return "yes"
    if v in {"no", "false", "n"}:
        return "no"
    return "unknown"


@dataclass(slots=True)
class ApiRecord:
    name: str
    description: str
    auth: str  # none | apikey | oauth | <other>
    https: str  # yes | no | unknown
    cors: str  # yes | no | unknown
    category: str
    url: str
    favorite: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ApiRecord":
        return cls(
            name=d.get("name", ""),
            description=d.get("description", ""),
            auth=d.get("auth", "unknown"),
            https=d.get("https", "unknown"),
            cors=d.get("cors", "unknown"),
            category=d.get("category", "Uncategorized"),
            url=d.get("url", ""),
            favorite=bool(d.get("favorite", False)),
        )

    @property
    def is_https(self) -> bool:
        return self.https == "yes"


@dataclass(slots=True)
class Catalog:
    records: list[ApiRecord] = field(default_factory=list)
    fetched_at: str = ""

    def counts(self) -> dict[str, int]:
        seen: dict[str, int] = {}
        for r in self.records:
            seen[r.category] = seen.get(r.category, 0) + 1
        return seen


def parse_readme(markdown: str) -> list[ApiRecord]:
    """Extract every canonical API row from the public-apis README."""
    lines = markdown.splitlines()
    records: list[ApiRecord] = []

    category: str | None = None
    # Set while inside the real catalog (after the `## Index` marker).
    in_index = False
    i = 0
    total = len(lines)

    while i < total:
        raw = lines[i]
        line = raw.strip()

        h2 = _H2_RE.match(line)
        if h2:
            in_index = h2.group(1).strip().lower() == "index"
            category = None
            i += 1
            continue

        h3 = _CATEGORY_RE.match(line)
        if h3:
            category = h3.group(1).strip()
            i += 1
            continue

        # A markdown table is anchored on its `|:---|:---|` separator row; the
        # header sits on the line above it and may or may not start with a pipe.
        if in_index and category and _is_separator(_cells(line)):
            header = _cells(lines[i - 1]) if i > 0 else []
            normalized = [h.strip().strip("*_` ").lower() for h in header]
            # Require the canonical 5-column shape.
            if len(normalized) < 5 or tuple(normalized[:5]) != _EXPECTED_HEADERS:
                i += 1
                continue

            i += 1  # skip the separator row
            while i < total:
                row = lines[i].strip()
                if not row.startswith("|"):
                    break
                cells = _cells(row)
                if len(cells) < 5:
                    i += 1
                    continue

                m = _LINK_RE.match(cells[0])
                if not m:
                    i += 1
                    continue
                name, url = m.group(1).strip(), m.group(2).strip()
                if not name:
                    i += 1
                    continue

                records.append(
                    ApiRecord(
                        name=name,
                        description=cells[1].replace("<br>", " ").strip(),
                        auth=normalize_auth(cells[2]),
                        https=normalize_flag(cells[3]),
                        cors=normalize_flag(cells[4]),
                        category=category,
                        url=url,
                    )
                )
                i += 1
            continue

        i += 1

    return records