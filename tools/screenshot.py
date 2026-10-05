"""Render the main window to a PNG without ever showing a window.

    python tools/screenshot.py [out.png] [table|cards]

Tiling window managers (Hyprland, glazewm, river, ...) aggressively manage any
mapped top-level window, which fights `resize()` and makes captures
non-deterministic. Setting `Qt.WA_DontShowOnScreen` makes Qt lay the widget out
and paint it into an offscreen surface *without mapping it to the screen*, so no
window manager ever sees it. This keeps captures reproducible under any WM and
in CI.

It also runs on the native platform plugin, so the bundled Inter / JetBrains
Mono faces resolve instead of falling back to tofu boxes (which is what the
`offscreen` plugin produces, since it ships no fonts).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Force the native plugin: it provides real system fonts.
os.environ.pop("QT_QPA_PLATFORM", None)

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from qtapis import fonts, theme  # noqa: E402
from qtapis.mainwindow import MainWindow  # noqa: E402
from qtapis.models import COL_NAME  # noqa: E402
from qtapis.store import load_catalog  # noqa: E402

WIDTH, HEIGHT = 1440, 880


def _settle(app, rounds: int = 12) -> None:
    for _ in range(rounds):
        app.processEvents()


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "screenshot.png"
    mode = sys.argv[2] if len(sys.argv) > 2 else "table"

    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    fonts.register_bundled_fonts()
    app.setStyleSheet(theme.stylesheet())

    win = MainWindow(load_catalog())

    # Never map the window: the WM cannot manage what it cannot see.
    win.setAttribute(Qt.WA_DontShowOnScreen, True)
    win.resize(WIDTH, HEIGHT)
    win.show()  # lays out, but WA_DontShowOnScreen keeps it off-screen
    _settle(app)

    if mode == "cards":
        win.set_view_mode("cards")
    else:
        win.table_view.selectRow(2)
    _settle(app)

    # Deferred card rebuilds land on the next event-loop turn.
    win.resize(WIDTH, HEIGHT)
    _settle(app)
    win.table_view.scrollTo(win.proxy.index(0, COL_NAME))
    _settle(app)

    if win.width() != WIDTH or win.height() != HEIGHT:
        print(f"layout did not settle: {win.width()}x{win.height()} "
              f"(expected {WIDTH}x{HEIGHT})", file=sys.stderr)
        return 1

    shot = win.grab()
    if shot.isNull():
        print("grab() returned a null pixmap", file=sys.stderr)
        return 1
    if not shot.save(str(out)):
        print(f"could not write {out}", file=sys.stderr)
        return 1

    print(f"Wrote {out} ({shot.width()}x{shot.height()}, "
          f"{out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())