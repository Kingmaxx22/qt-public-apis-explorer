"""Resource paths that work from source and from a frozen bundle.

PyInstaller extracts bundled data to a temporary directory and exposes it via
`sys._MEIPASS`. Reading `__file__` alone would point into the wrong place once
frozen, so everything resolves through here.
"""

from __future__ import annotations

import sys
from pathlib import Path


def bundle_dir() -> Path:
    """Root of the running application.

    - Frozen (PyInstaller): the extraction directory holding bundled data.
    - From source: the repository root (the parent of this package).
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent.parent


def asset(*parts: str) -> Path:
    """Path to a bundled asset, e.g. asset('fonts', 'Inter-Regular.ttf')."""
    return bundle_dir().joinpath("assets", *parts)


def data_file(*parts: str) -> Path:
    """Path to bundled data, e.g. data_file('catalog.json')."""
    return bundle_dir().joinpath("data", *parts)


def writable_data_path() -> Path:
    """A writable location for the catalog cache.

    A frozen onefile bundle extracts to a read-only temp directory, so the
    cache is written next to the executable instead.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "data"
    return bundle_dir() / "data"