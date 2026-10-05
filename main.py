"""Qt Public APIs Explorer — entry point."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtWidgets import QApplication

from qtapis import fonts, theme


def _selftest(out_path: str) -> int:
    """Verify a frozen build end-to-end and write a JSON report.

    Useful because a windowed build has no stdout: this is the only way to
    confirm the packaged app actually loads its bundled data and fonts.

        QtPublicAPIs.exe --selftest report.json
    """
    from qtapis.store import load_catalog, BUNDLED_SNAPSHOT

    report: dict = {"ok": False}
    try:
        catalog = load_catalog()
        report["records"] = len(catalog.records)
        report["categories"] = len(catalog.counts())
        report["bundled_snapshot"] = str(BUNDLED_SNAPSHOT)
        report["snapshot_exists"] = BUNDLED_SNAPSHOT.exists()
        report["fonts"] = fonts.available()
        report["sans_family"] = theme.sans_family()
        report["mono_family"] = theme.mono_family()
        first = catalog.records[0]
        report["first_record"] = {
            "name": first.name,
            "auth": first.auth,
            "https": first.https,
            "cors": first.cors,
        }
        report["ok"] = (
            report["records"] > 0
            and report["snapshot_exists"]
            and "Inter" in report["fonts"]
            and "JetBrains Mono" in report["fonts"]
        )
    except Exception as exc:  # noqa: BLE001 - the report is the deliverable
        report["error"] = f"{type(exc).__name__}: {exc}"

    Path(out_path).write_text(json.dumps(report, indent=1), encoding="utf-8")
    return 0 if report["ok"] else 1


def main() -> int:
    if "--selftest" in sys.argv:
        idx = sys.argv.index("--selftest")
        target = sys.argv[idx + 1] if len(sys.argv) > idx + 1 else "selftest.json"
        # A QApplication is still needed for font registration to work.
        app = QApplication.instance() or QApplication(sys.argv[:idx])
        fonts.register_bundled_fonts()
        return _selftest(target)

    from qtapis.mainwindow import launch

    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    # Register the bundled faces *before* building the stylesheet so the family
    # lookups inside it resolve to the real design fonts.
    fonts.register_bundled_fonts()
    app.setStyleSheet(theme.stylesheet())
    return launch()


if __name__ == "__main__":
    raise SystemExit(main())