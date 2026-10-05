"""Measure real OS thread counts for the app, using the Win32 toolhelp API.

    python tools/thread_audit.py

Answers whether the explorer leaks threads, rather than guessing from
Task Manager. Runs headless (offscreen) so no window is ever mapped.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ctypes  # noqa: E402
import ctypes.wintypes as wt  # noqa: E402

TH32CS_SNAPTHREAD = 0x00000004
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class THREADENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD),
        ("cntUsage", wt.DWORD),
        ("th32ThreadID", wt.DWORD),
        ("th32OwnerProcessID", wt.DWORD),
        ("tpBasePri", ctypes.c_long),
        ("tpDeltaPri", ctypes.c_long),
        ("dwFlags", wt.DWORD),
    ]


def thread_count() -> int:
    """Count live threads owned by this process via CreateToolhelp32Snapshot."""
    kernel32 = ctypes.windll.kernel32
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
    if snapshot == INVALID_HANDLE_VALUE:
        return -1
    try:
        entry = THREADENTRY32()
        entry.dwSize = ctypes.sizeof(THREADENTRY32)
        me = os.getpid()
        count = 0
        if kernel32.Thread32First(snapshot, ctypes.byref(entry)):
            while True:
                if entry.th32OwnerProcessID == me:
                    count += 1
                if not kernel32.Thread32Next(snapshot, ctypes.byref(entry)):
                    break
        return count
    finally:
        kernel32.CloseHandle(snapshot)


def settle(app, rounds: int = 8) -> None:
    for _ in range(rounds):
        app.processEvents()


def report(label: str, app) -> None:
    settle(app)
    print(f"  {label:<46} {thread_count():>4} threads")


def main() -> int:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from qtapis import fonts, theme
    from qtapis.store import load_catalog

    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    fonts.register_bundled_fonts()
    app.setStyleSheet(theme.stylesheet())

    print(f"pid {os.getpid()}")
    report("bare interpreter", app)

    from qtapis.mainwindow import MainWindow

    report("after importing mainwindow", app)

    catalog = load_catalog()
    report("after loading the 2,020-record catalog", app)

    win = MainWindow(catalog)
    win.resize(1200, 800)
    win.show()
    report("after building the full window", app)

    # Hammer the filter/sort paths, which allocate per-row view objects.
    for term in ("cat", "dog", "api", "weather", ""):
        win.search.setText(term)
        settle(app, 4)
    win.table_view.sortByColumn(2, Qt.AscendingOrder)
    settle(app, 6)
    report("after search + sort churn", app)

    win.set_view_mode("cards")
    settle(app, 10)
    report("after building the card view", app)

    # Run repeated background syncs and confirm threads come back down.
    from qtapis.sync import SyncController

    sync_mod = __import__("qtapis.sync", fromlist=["x"])
    fixture = (
        "## Index\n\n* [Animals](#animals)\n\n### Animals\n"
        "API | Description | Auth | HTTPS | CORS\n"
        "|:---|:---|:---|:---|:---|\n"
        "| [Fixture](https://example.com) | d | No | Yes | Yes |\n"
    )
    real_fetch = sync_mod.fetch_markdown
    real_save = sync_mod.save_snapshot
    sync_mod.fetch_markdown = lambda: fixture
    sync_mod.save_snapshot = lambda cat, path=None: None

    probe = SyncController()
    for _ in range(12):
        probe.start()
        deadline = time.time() + 10
        while probe.busy and time.time() < deadline:
            app.processEvents()
            time.sleep(0.01)
    probe.shutdown()
    settle(app, 20)
    report("after 12 sequential background syncs", app)

    sync_mod.fetch_markdown = real_fetch
    sync_mod.save_snapshot = real_save
    win.sync.shutdown()
    settle(app, 10)
    report("after tearing the window's controller down", app)

    win.close()
    settle(app, 10)
    final = thread_count()
    report("after closing the window", app)
    print(f"\n  final={final} baseline_measured_above")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())