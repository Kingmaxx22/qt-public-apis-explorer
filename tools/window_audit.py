"""Enumerate every top-level widget the app creates during startup.

    python tools/window_audit.py

A process audit only counts OS processes, but one process can own many
top-level widgets -- and each mapped top-level window becomes a separate
tile for a tiling WM. This walks QApplication.topLevelWidgets() on a tight
timer and records every distinct window that appears, with its class, title,
geometry and window flags.

Every widget gets Qt.WA_DontShowOnScreen, so Qt lays out and paints them
without mapping a native window. Nothing is created for the WM to manage,
so this is safe to run under glazewm.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt, QPoint  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402


def describe(w: QWidget) -> str:
    flags = int(w.windowFlags())
    frameless = bool(flags & int(Qt.FramelessWindowHint))
    titled = bool(flags & int(Qt.WindowTitleHint))
    tool = bool(flags & int(Qt.Tool))
    popup = bool(flags & int(Qt.Popup))
    geo = w.geometry()
    return (
        f"class={type(w).__name__:<22} title={w.windowTitle()!r:<28} "
        f"visible={int(w.isVisible())} frameless={int(frameless)} "
        f"titled={int(titled)} tool={int(tool)} popup={int(popup)} "
        f"size={geo.width()}x{geo.height()}"
    )


def hide_all(app) -> None:
    """Stop any top-level widget from ever mapping a native window."""
    for w in app.topLevelWidgets():
        w.setAttribute(Qt.WA_DontShowOnScreen, True)


def main() -> int:
    from qtapis import fonts, theme

    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    fonts.register_bundled_fonts()
    app.setStyleSheet(theme.stylesheet())

    from qtapis.mainwindow import MainWindow
    from qtapis.store import load_catalog

    seen: set[int] = set()
    log: list[tuple[float, str]] = []
    t0 = time.perf_counter()

    def poll() -> None:
        for w in app.topLevelWidgets():
            if id(w) in seen:
                continue
            seen.add(id(w))
            w.setAttribute(Qt.WA_DontShowOnScreen, True)
            log.append(((time.perf_counter() - t0) * 1000.0, describe(w)))

    poll()
    catalog = load_catalog()
    poll()
    win = MainWindow(catalog)
    poll()
    win.show()
    poll()

    for _ in range(40):
        app.processEvents()
        poll()
        time.sleep(0.01)

    # Drive the interactions most likely to spawn a stray top-level window.
    win.search.setText("weather")
    for _ in range(10):
        app.processEvents()
        poll()
    win.set_view_mode("cards")
    for _ in range(20):
        app.processEvents()
        poll()
    win.table_view.sortByColumn(2, Qt.AscendingOrder)
    for _ in range(10):
        app.processEvents()
        poll()
    hide_all(app)
    win.close()
    for _ in range(10):
        app.processEvents()
        poll()

    print(f"\n{len(log)} distinct top-level widget(s) created:\n")
    for ms, desc in log:
        print(f"  +{ms:8.1f} ms  {desc}")

    strays = [d for _, d in log if "title='Qt Public APIs Explorer'" in d
              and "class=MainWindow" not in d]
    print(f"\n  stray titled windows: {len(strays)}")
    for s in strays:
        print(f"    {s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())