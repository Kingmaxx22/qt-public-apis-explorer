"""Register the bundled Inter + JetBrains Mono faces with Qt.

Both families ship under the SIL Open Font License (see assets/fonts/OFL-*.txt).
Registering them at startup makes the rendered interface match design/design.md
on any machine, instead of silently falling back to Segoe UI / Consolas.
"""

from __future__ import annotations

import logging

from PySide6.QtGui import QFontDatabase

from .paths import asset

FONT_DIR = asset("fonts")

# Preferred family name -> bundled file stems, lightest first.
FAMILIES: dict[str, tuple[str, ...]] = {
    "Inter": ("Inter-Regular", "Inter-Medium", "Inter-SemiBold", "Inter-Bold"),
    "JetBrains Mono": (
        "JetBrainsMono-Regular",
        "JetBrainsMono-Medium",
        "JetBrainsMono-SemiBold",
        "JetBrainsMono-Bold",
    ),
}

_registered: dict[str, str] = {}


def register_bundled_fonts() -> dict[str, str]:
    """Load every bundled face. Returns family -> resolved family name."""
    global _registered
    if _registered:
        return _registered

    for family, stems in FAMILIES.items():
        loaded = False
        for stem in stems:
            path = FONT_DIR / f"{stem}.ttf"
            if not path.exists():
                logging.getLogger(__name__).debug(
                    "bundled font missing, skipping: %s", path.name
                )
                continue
            font_id = QFontDatabase.addApplicationFont(str(path))
            if font_id == -1:
                logging.getLogger(__name__).warning(
                    "Qt rejected bundled font: %s", path.name
                )
                continue
            loaded = True
        if loaded:
            _registered[family] = family

    return dict(_registered)


def available() -> dict[str, str]:
    """Family -> resolved name, for diagnostics."""
    return dict(_registered)