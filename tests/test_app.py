"""End-to-end GUI checks for the Qt Public APIs Explorer.

Runs against the offscreen Qt platform so it works over SSH / in CI.

    python tests/test_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import csv  # noqa: E402
import time  # noqa: E402

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtGui import QFontDatabase  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from qtapis import fonts as fonts_mod  # noqa: E402
from qtapis import theme  # noqa: E402
from qtapis.curlgen import build_curl  # noqa: E402
from qtapis.mainwindow import MainWindow  # noqa: E402
from qtapis.models import (  # noqa: E402
    COL_ACTIONS,
    COL_CORS,
    COL_FAVORITE,
    COL_HTTPS,
    COL_NAME,
)
from qtapis.store import load_catalog  # noqa: E402
from qtapis.widgets import ALL_APIS, FAVORITES  # noqa: E402

PASS, FAIL = [], []

# `--live` lets the sync tests hit GitHub for real. Off by default so the suite
# stays hermetic, fast, and network-friendly.
LIVE = "--live" in sys.argv

# Minimal upstream-shaped README used to drive worker threads without the network.
_README_FIXTURE = """
# Fixture

## Index

* [Animals](#animals)

### Animals
API | Description | Auth | HTTPS | CORS
|:---|:---|:---|:---|:---|
| [Fixture Dog](https://example.com/dog) | A fixture endpoint | No | Yes | Yes |
| [Fixture Cat](https://example.com/cat) | Another fixture | `apiKey` | Yes | No |
"""


def check(label: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(label)
    mark = "PASS" if condition else "FAIL"
    print(f"[{mark}] {label}" + (f"  -> {detail}" if detail else ""))


def main() -> int:
    # The console may be cp1252; the suite prints glyphs like the restore
    # symbol, so don't let encoding kill the run.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    fonts_mod.register_bundled_fonts()
    app.setStyleSheet(theme.stylesheet())

    # Never let a test open a real browser window: record the request instead.
    opened_urls: list[str] = []

    from PySide6.QtGui import QDesktopServices

    QDesktopServices.openUrl = staticmethod(  # type: ignore[assignment]
        lambda url: (opened_urls.append(url.toString()), True)[1]
    )

    catalog = load_catalog()
    win = MainWindow(catalog)
    win.show()
    app.processEvents()

    total = len(catalog.records)
    check("catalog loads a full registry", total > 1000, f"{total} records")
    check("grid is populated", win.proxy.rowCount() == total,
          f"{win.proxy.rowCount()} rows")
    check("grid has 9 columns", win.proxy.columnCount() == 9)
    check("sidebar lists all categories",
          win.tree.topLevelItemCount() == len(catalog.counts()) + 2,
          f"{win.tree.topLevelItemCount()} items")

    # -- search ----------------------------------------------------------
    win.search.setText("cat")
    app.processEvents()
    search_rows = win.proxy.rowCount()
    check("search narrows the grid", 0 < search_rows < total,
          f"{search_rows} rows for 'cat'")

    def haystack(r: int) -> str:
        rec = win.proxy.index(r, 0).data(Qt.UserRole)
        return " ".join(
            (rec.name, rec.description, rec.category, rec.url)
        ).lower()

    offenders = [r for r in range(search_rows) if "cat" not in haystack(r)]
    check("every search hit actually contains the term", not offenders,
          f"{len(offenders)} offenders" if offenders else "all match")

    win.search.setText("")
    app.processEvents()
    check("clearing search restores the grid", win.proxy.rowCount() == total)

    # -- toolbar filters --------------------------------------------------
    win.auth_combo.setCurrentIndex(3)  # OAuth
    app.processEvents()
    oauth_rows = win.proxy.rowCount()
    check("auth filter applies", 0 < oauth_rows < total, f"{oauth_rows} OAuth")
    check("auth filter is exact",
          all(win.proxy.index(r, 4).data(Qt.UserRole).auth == "oauth"
              for r in range(oauth_rows)))
    win.auth_combo.setCurrentIndex(0)
    app.processEvents()

    win.https_btn.setChecked(True)
    app.processEvents()
    secure_rows = win.proxy.rowCount()
    check("HTTPS toggle applies", 0 < secure_rows < total,
          f"{secure_rows} HTTPS-only")
    check("HTTPS filter is exact",
          all(win.proxy.index(r, 5).data(Qt.UserRole).https == "yes"
              for r in range(secure_rows)))
    win.https_btn.setChecked(False)
    app.processEvents()

    win.cors_combo.setCurrentIndex(1)  # CORS YES
    app.processEvents()
    cors_rows = win.proxy.rowCount()
    check("CORS filter applies", 0 < cors_rows < total, f"{cors_rows} CORS-enabled")
    win.cors_combo.setCurrentIndex(0)
    app.processEvents()

    # -- combined filters -------------------------------------------------
    win.search.setText("api")
    win.https_btn.setChecked(True)
    app.processEvents()
    combined = win.proxy.rowCount()
    check("filters combine (AND)", combined <= secure_rows, f"{combined} rows")
    win.reset_filters()
    app.processEvents()
    check("reset restores every row", win.proxy.rowCount() == total)

    # -- category navigation ----------------------------------------------
    target = "Animals"
    win._on_category_selected(target)
    app.processEvents()
    cat_rows = win.proxy.rowCount()
    check("category filter applies", cat_rows == catalog.counts()[target],
          f"{cat_rows} in {target}")
    check("category filter is exact",
          all(win.proxy.index(r, 7).data(Qt.UserRole).category == target
              for r in range(cat_rows)))

    win._on_category_selected(ALL_APIS)
    app.processEvents()
    check("All APIs restores the grid", win.proxy.rowCount() == total)

    # -- selection -> inspector -------------------------------------------
    win.table_view.selectRow(0)
    app.processEvents()
    record = win._selected_record()
    check("selecting a row loads the inspector",
          record is not None and win.inspector._record is record,
          record.name if record else "none")
    check("inspector shows the cURL well",
          getattr(win.inspector, "curl_edit", None) is not None)
    if record is not None:
        curl_text = win.inspector.curl_edit.toPlainText()
        check("cURL references the endpoint", record.url in curl_text,
              curl_text[:70])
        check("cURL has the curl verb", curl_text.startswith("curl "))

    # -- cURL generation ---------------------------------------------------
    oauth_rec = next((r for r in catalog.records if r.auth == "oauth"), None)
    if oauth_rec:
        cmd = build_curl(oauth_rec)
        check("OAuth cURL injects a bearer header",
              "Authorization" in cmd and "Bearer" in cmd, cmd[:80])
    insecure = next((r for r in catalog.records if r.https == "no"), None)
    if insecure:
        check("insecure endpoint is flagged in the cURL",
              "WARNING" in build_curl(insecure))

    # -- copy to clipboard -------------------------------------------------
    if record is not None:
        win._copy_selected_curl()
        app.processEvents()
        check("copy puts the cURL on the clipboard",
              build_curl(record) in QApplication.clipboard().text())

    # -- favorites ----------------------------------------------------------
    if record is not None:
        before = win.store.favorite_count()
        win._toggle_selected_favorite()
        app.processEvents()
        check("favorite toggles", win.store.favorite_count() == before + 1)
        win._on_category_selected(FAVORITES)
        app.processEvents()
        check("Favorites view lists the favorited API",
              win.proxy.rowCount() == before + 1,
              f"{win.proxy.rowCount()} favorite(s)")
        check("Favorites view is exact",
              all(win.proxy.index(r, 0).data(Qt.UserRole).favorite
                  for r in range(win.proxy.rowCount())))
        win._on_category_selected(ALL_APIS)
        app.processEvents()

    # -- sorting -------------------------------------------------------------
    win.table_view.sortByColumn(COL_NAME, Qt.AscendingOrder)
    app.processEvents()
    sorted_names = [win.proxy.index(r, COL_NAME).data(Qt.DisplayRole)
                    for r in range(min(200, win.proxy.rowCount()))]
    expected = sorted(sorted_names, key=str.lower)
    ok = sorted_names == expected
    detail = ""
    if not ok:
        first_bad = next(
            (i for i in range(len(sorted_names))
             if sorted_names[i] != expected[i]), 0)
        detail = (f"idx={first_bad} got={sorted_names[first_bad]!r} "
                  f"want={expected[first_bad]!r} "
                  f"prev={sorted_names[first_bad - 1]!r}")
    check("name sort is ordered", ok, detail)

    win.table_view.sortByColumn(COL_HTTPS, Qt.DescendingOrder)
    app.processEvents()
    https_col = [win.proxy.index(r, COL_HTTPS).data(Qt.UserRole).https
                 for r in range(min(200, win.proxy.rowCount()))]
    # rank(yes)=0 < rank(no)=1 < rank(unknown)=2, so descending puts 'no' first.
    check("HTTPS sort reverses the rank order", https_col[0] == "no",
          f"first={https_col[0]}")
    win.table_view.sortByColumn(COL_HTTPS, Qt.AscendingOrder)
    app.processEvents()
    https_asc = [win.proxy.index(r, COL_HTTPS).data(Qt.UserRole).https
                 for r in range(min(200, win.proxy.rowCount()))]
    check("HTTPS sort ascending leads with 'yes'", https_asc[0] == "yes",
          f"first={https_asc[0]}")

    win.table_view.sortByColumn(COL_CORS, Qt.AscendingOrder)
    app.processEvents()
    cors_col = [win.proxy.index(r, COL_CORS).data(Qt.UserRole).cors
                for r in range(min(200, win.proxy.rowCount()))]
    check("CORS sort ascending leads with 'yes'", cors_col[0] == "yes",
          f"first={cors_col[0]}")

    # -- export helpers ------------------------------------------------------
    import json as _json
    import tempfile as _tempfile

    visible = win._visible_records()
    check("export enumerates visible rows", len(visible) == win.proxy.rowCount())
    with _tempfile.TemporaryDirectory() as tmp:
        json_path = Path(tmp) / "out.json"
        json_path.write_text(
            _json.dumps([r.to_dict() for r in visible[:5]]), encoding="utf-8"
        )
        check("JSON export is valid", len(_json.loads(
            json_path.read_text(encoding="utf-8"))) == 5)

    # -- inline row actions --------------------------------------------------
    from qtapis.delegates import ApiDelegate

    header = win.table_view.horizontalHeader()
    row0 = win.proxy.index(0, COL_ACTIONS)
    rec0 = row0.data(Qt.UserRole)

    win._on_action_clicked(row0, ApiDelegate.ACTION_INSPECT)
    app.processEvents()
    check("inspect action loads the row into the inspector",
          win.inspector._record is rec0, rec0.name)

    win._on_action_clicked(row0, ApiDelegate.ACTION_COPY)
    app.processEvents()
    check("copy action puts the row's cURL on the clipboard",
          build_curl(rec0) in QApplication.clipboard().text())

    fav_before = win.store.favorite_count()
    win._on_action_clicked(win.proxy.index(0, COL_FAVORITE), 0)  # no-op guard
    app.processEvents()
    check("action handler ignores an out-of-range index gracefully",
          win.store.favorite_count() == fav_before)

    # -- column visibility toggle ---------------------------------------------
    from qtapis.models import COL_DESCRIPTION

    check("all 9 columns start visible",
          not header.isSectionHidden(COL_DESCRIPTION))
    win._cycle_columns()
    app.processEvents()
    check("columns button hides the description",
          header.isSectionHidden(COL_DESCRIPTION)
          and win.columns_btn.text() == "Columns (8/9)",
          win.columns_btn.text())
    win._cycle_columns()
    app.processEvents()
    check("columns button restores the description",
          not header.isSectionHidden(COL_DESCRIPTION)
          and win.columns_btn.text() == "Columns (9/9)",
          win.columns_btn.text())

    # -- copy all visible -----------------------------------------------------
    win.search.setText("cat")
    app.processEvents()
    win._copy_all_curl()
    app.processEvents()
    clipboard = QApplication.clipboard().text()
    visible_n = win.proxy.rowCount()
    check("copy-all emits one cURL per visible row",
          clipboard.count("curl -sS -L") == visible_n,
          f"{clipboard.count('curl -sS -L')} commands for {visible_n} rows")
    win.reset_filters()
    app.processEvents()

    # -- export (drives the real method with a patched file dialog) ----------
    import tempfile

    from PySide6.QtWidgets import QFileDialog

    tmpdir = tempfile.mkdtemp()
    csv_path = Path(tmpdir) / "export.csv"
    original_get = QFileDialog.getSaveFileName
    QFileDialog.getSaveFileName = staticmethod(
        lambda *a, **k: (str(csv_path), "CSV files (*.csv)")
    )
    try:
        win.search.setText("weather")
        app.processEvents()
        expected_rows = win.proxy.rowCount()
        win.export_catalog()
        app.processEvents()
    finally:
        QFileDialog.getSaveFileName = original_get

    check("export_catalog wrote a file", csv_path.exists())
    if csv_path.exists():
        with open(csv_path, encoding="utf-8", newline="") as fh:
            rows = list(csv.reader(fh))
        check("export_catalog respects the active filter",
              len(rows) - 1 == expected_rows and 0 < expected_rows,
              f"{len(rows) - 1} rows exported, {expected_rows} visible")
        check("export_csv has the documented header",
              rows[0] == ["Name", "Description", "Auth", "HTTPS", "CORS",
                          "Category", "URL"],
              str(rows[0]))
    win.reset_filters()
    app.processEvents()

    # -- refresh from GitHub (background thread) -----------------------------
    from qtapis import store as store_mod
    import qtapis.sync as sync_mod
    import qtapis.mainwindow as mw_mod

    calls = {"n": 0, "threads": set()}
    real_fetch = store_mod.fetch_markdown

    def counting_fetch():
        import threading

        calls["n"] += 1
        calls["threads"].add(threading.current_thread().name)
        # Stay off the network unless --live is passed; this keeps the suite
        # fast and avoids hammering GitHub on every run.
        if LIVE:
            return real_fetch()
        return _README_FIXTURE

    sync_mod.fetch_markdown = counting_fetch
    saved = {}

    def spy_save(cat, path=store_mod.SNAPSHOT_PATH):
        saved["count"] = len(cat.records)
        saved["stamp"] = cat.fetched_at
        if LIVE:
            return path
        return path  # never touch the real snapshot in offline mode

    sync_mod.save_snapshot = spy_save
    outcome = {}

    def on_done(cat):
        outcome["catalog"] = cat

    def on_fail(msg):
        outcome["error"] = msg

    win.sync.finished.connect(on_done)
    win.sync.failed.connect(on_fail)

    urls_before_sync = len(opened_urls)
    started = win.refresh_catalog()
    app.processEvents()
    check("refresh starts", started)
    check("refresh runs off the GUI thread",
          calls["threads"] and "MainThread" not in calls["threads"],
          ", ".join(sorted(calls["threads"])) or "pending")

    # The UI must stay responsive while the worker runs.
    interactive = {"ok": False}
    if win.sync.busy:
        win.search.setText("dog")
        app.processEvents()
        interactive["ok"] = win.proxy.rowCount() < total
    check("UI stays interactive during a sync", interactive["ok"],
          "filtered while worker ran")
    win.reset_filters()
    app.processEvents()

    deadline = time.time() + 90
    while win.sync.busy and time.time() < deadline:
        app.processEvents()
        time.sleep(0.02)
    app.processEvents()

    sync_mod.fetch_markdown = real_fetch
    sync_mod.save_snapshot = store_mod.save_snapshot

    check("refresh hit the network exactly once", calls["n"] == 1,
          f"{calls['n']} fetch(es)")
    check("refresh produced a full catalog",
          saved.get("count", 0) > (1000 if LIVE else 1),
          f"{saved.get('count')} records")
    check("refresh stamps the catalog", bool(saved.get("stamp")),
          str(saved.get("stamp")))
    check("refresh delivers the catalog to the window",
          outcome.get("catalog") is not None
          and not outcome.get("error"),
          outcome.get("error", "ok"))
    check("refresh repopulates the grid",
          win.proxy.rowCount() == saved.get("count", 0),
          f"{win.proxy.rowCount()} rows shown")
    check("no browser window was opened during sync",
          len(opened_urls) == urls_before_sync,
          f"{len(opened_urls) - urls_before_sync} opened")
    # Restore the full catalog so later assertions see the real registry
    # rather than the 2-row fixture.
    win._apply_catalog(catalog)
    app.processEvents()
    check("grid is restored after the sync test",
          win.proxy.rowCount() == total, f"{win.proxy.rowCount()} rows")
    check("refresh re-enables the sync button", win.sync_btn.isEnabled())
    check("controller reports idle after finishing", not win.sync.busy)

    # A second refresh while one is running must be refused. Use a fixture rather
    # than the live network so this cannot outlive the event loop.
    from qtapis.sync import SyncController

    probe = SyncController()
    real_fetch_for_probe = sync_mod.fetch_markdown
    real_save_for_probe = sync_mod.save_snapshot
    sync_mod.fetch_markdown = lambda: _README_FIXTURE
    # Never let the fixture reach data/catalog.json.
    sync_mod.save_snapshot = lambda cat, path=None: None
    check("a fresh controller can start", probe.start() is True)
    check("an overlapping start is refused", probe.start() is False)
    deadline = time.time() + 30
    while probe.busy and time.time() < deadline:
        app.processEvents()
        time.sleep(0.02)
    probe.shutdown()
    sync_mod.fetch_markdown = real_fetch_for_probe
    sync_mod.save_snapshot = real_save_for_probe

    # -- editable endpoint ---------------------------------------------------
    if record is not None:
        from qtapis.curlgen import build_curl as build_curl2

        win.table_view.selectRow(0)
        app.processEvents()
        rec = win._selected_record()
        win.inspector.set_record(rec)
        app.processEvents()
        ep = win.inspector.endpoint_edit
        check("inspector exposes an editable endpoint",
              ep is not None and ep.text() == rec.url,
              ep.text() if ep else "missing")

        ep.setText("https://api.example.com/v1/animals")
        app.processEvents()
        rebuilt = win.inspector.curl_edit.toPlainText()
        check("endpoint edit regenerates the command",
              "https://api.example.com/v1/animals" in rebuilt,
              rebuilt[:70])
        check("endpoint edit preserves the auth header",
              "X-API-Key" in rebuilt or "Authorization" in rebuilt
              or rec.auth in ("none", "unknown"),
              rec.auth)
        check("endpoint edit marks itself as custom",
              "Custom endpoint" in win.inspector.endpoint_note.text(),
              win.inspector.endpoint_note.text())

        win.inspector._reset_endpoint()
        app.processEvents()
        check("endpoint reset restores the registry link",
              win.inspector.endpoint_edit.text() == rec.url
              and rec.url in win.inspector.curl_edit.toPlainText(),
              win.inspector.endpoint_edit.text())

        win.inspector.copy_curl()
        app.processEvents()
        check("copy uses the live endpoint value",
              win.inspector.curl_edit.toPlainText()
              in QApplication.clipboard().text())

        insecure = next((r for r in catalog.records if r.https == "no"), None)
        if insecure:
            cmd = build_curl2(insecure, "http://plain.example.com/x")
            check("non-https override is flagged",
                  "--insecure" in cmd and "WARNING" in cmd, cmd[:80])

        mashape = next((r for r in catalog.records
                        if r.auth == "x-mashape-key"), None)
        if mashape:
            check("exotic auth scheme still gets a header",
                  "X-Mashape-Key" in build_curl2(mashape), mashape.auth)

    # -- card view ------------------------------------------------------------
    from qtapis.mainwindow import CARD_PAGE_SIZE

    win.reset_filters()
    app.processEvents()
    check("table mode is the default", win._view_mode == "table"
          and win.table_view.isVisible())

    win.set_view_mode("cards")
    app.processEvents()
    check("card view shows cards", win.card_view.card_count() > 0,
          f"{win.card_view.card_count()} cards")
    check("card view hides the table", not win.table_view.isVisible())
    check("card view caps the page", win.card_view.card_count()
          == min(win.proxy.rowCount(), CARD_PAGE_SIZE))
    check("card caption reports the cap",
          "shown" in win.card_caption.text(), win.card_caption.text())
    check("Columns/Fit are disabled in card view",
          not win.columns_btn.isEnabled() and not win.fit_btn.isEnabled())

    card0 = win.card_view.card_at(0)
    win._on_card_activated(card0.record)
    app.processEvents()
    check("activating a card loads the inspector",
          win.inspector._record is card0.record, card0.record.name)

    win.search.setText("dog")
    app.processEvents()
    win.set_view_mode("cards")
    app.processEvents()
    check("card view respects the search filter",
          win.card_view.card_count() == win.proxy.rowCount(),
          f"{win.card_view.card_count()} cards / {win.proxy.rowCount()} rows")

    win.set_view_mode("table")
    app.processEvents()
    check("switching back restores the table", win.table_view.isVisible()
          and not win.card_view.isVisible())
    check("Columns/Fit re-enable in table view",
          win.columns_btn.isEnabled() and win.fit_btn.isEnabled())
    win.reset_filters()
    app.processEvents()

    # -- URL opening must never reach a real browser -------------------------
    win.table_view.selectRow(0)
    app.processEvents()
    before = len(opened_urls)
    win._open_selected()
    app.processEvents()
    check("open documentation is routed through the stub",
          len(opened_urls) == before + 1,
          f"{len(opened_urls) - before} recorded")
    check("stubbed URL matches the record",
          opened_urls and win._selected_record().url in opened_urls[-1],
          opened_urls[-1] if opened_urls else "none")

    # -- frameless window chrome ----------------------------------------------
    check("window is frameless so only the themed bar is drawn",
          bool(win.windowFlags() & Qt.FramelessWindowHint))

    # Qt keeps WindowTitleHint in the bitmask even when frameless (it is just
    # ignored), so assert on the observable outcome instead: no native frame
    # is reserved, so frame and client geometry coincide.
    check("no native frame is reserved",
          win.frameGeometry() == win.geometry(),
          f"frame={win.frameGeometry().getRect()} client={win.geometry().getRect()}")

    # The themed bar really is the topmost chrome.
    check("themed title bar sits at the top of the window",
          win.title_bar.geometry().top() == 0
          and win.title_bar.height() == theme.TITLEBAR_H,
          f"top={win.title_bar.geometry().top()} h={win.title_bar.height()}")

    # Title bar buttons must drive real window state, not be decorative.
    win.title_bar._winMax.click()
    app.processEvents()
    check("maximize button maximizes", win.isMaximized())
    check("maximize glyph reflects state",
          win.title_bar._winMax.text() == "❐",
          win.title_bar._winMax.text())
    win.title_bar._winMax.click()
    app.processEvents()
    check("maximize button restores", not win.isMaximized())
    check("maximize glyph resets",
          win.title_bar._winMax.text() == "□",
          win.title_bar._winMax.text())

    win.toggle_maximized()
    app.processEvents()
    check("double-click / toggle path maximizes", win.isMaximized())
    win.toggle_maximized()
    app.processEvents()
    check("toggle path restores", not win.isMaximized())

    # Edge hit-testing drives the frameless resize grip.
    frame = win.frameGeometry()
    centre = frame.center()
    check("no edge detected away from the border",
          win._edge_at(centre) is None, str(win._edge_at(centre)))
    check("left edge detected",
          win._edge_at(QPoint(frame.left() + 2, centre.y())) == "left")
    check("right edge detected",
          win._edge_at(QPoint(frame.right() - 2, centre.y())) == "right")
    check("top edge detected",
          win._edge_at(QPoint(centre.x(), frame.top() + 2)) == "top")
    check("bottom edge detected",
          win._edge_at(QPoint(centre.x(), frame.bottom() - 2)) == "bottom")
    check("top-left corner detected",
          win._edge_at(QPoint(frame.left() + 1, frame.top() + 1))
          == "top-left")
    check("bottom-right corner detected",
          win._edge_at(QPoint(frame.right() - 1, frame.bottom() - 1))
          == "bottom-right")
    check("just outside the border is not an edge",
          win._edge_at(QPoint(frame.left() - 20, centre.y())) is None)

    # Resizing must respect the minimum size.
    win.resize(1200, 800)
    app.processEvents()
    win._resize_edge = "right"
    win._resize_origin = (win.geometry().x(), win.geometry().y(),
                          win.width(), win.height())
    win._resize_global = win.mapToGlobal(QPoint(win.width(), win.height() // 2))
    win._apply_resize(win._resize_global + QPoint(-900, 0))
    app.processEvents()
    check("resize clamps to the minimum width",
          win.width() == win.minimumWidth(),
          f"{win.width()} vs min {win.minimumWidth()}")
    win._end_resize()

    # The override-cursor stack must stay balanced across edge changes.
    win._set_hover_cursor("left")
    win._set_hover_cursor("top")
    win._set_hover_cursor(None)
    app.processEvents()
    check("hover cursor changes leave no override behind",
          QApplication.overrideCursor() is None,
          str(QApplication.overrideCursor()))

    # -- bundled fonts ---------------------------------------------------------
    check("bundled fonts registered",
          set(fonts_mod.available()) >= {"Inter", "JetBrains Mono"},
          str(fonts_mod.available()))
    check("sans resolves to the bundled Inter",
          theme.sans_family() == "Inter", theme.sans_family())
    check("mono resolves to the bundled JetBrains Mono",
          theme.mono_family() == "JetBrains Mono",
          theme.mono_family())
    check("every bundled face file exists",
          all((fonts_mod.FONT_DIR / f"{s}.ttf").exists()
              for stems in fonts_mod.FAMILIES.values() for s in stems))
    check("font licenses are bundled",
          (fonts_mod.FONT_DIR / "OFL-Inter.txt").exists()
          and (fonts_mod.FONT_DIR / "OFL-JetBrainsMono.txt").exists())

    # -- typography tokens map to the right family selector --------------------
    sans_family = theme.font("body-md").family()
    check("sans roles resolve to the sans family",
          theme.font("body-md").family() == theme.sans_family(),
          sans_family)
    check("code roles resolve to the mono family",
          theme.font("code-sm").family() == theme.mono_family(),
          theme.font("code-sm").family())
    check("every typography role builds without error",
          all(theme.font(role).family() for role in theme.TYPOGRAPHY),
          f"{len(theme.TYPOGRAPHY)} roles")
    check("families resolve to installed fonts on a real display",
          not QFontDatabase.families()
          or theme.sans_family() in QFontDatabase.families(),
          theme.sans_family())

    # -- layout toggles -------------------------------------------------------
    win._toggle_sidebar(False)
    app.processEvents()
    check("sidebar collapses", not win.sidebar.isVisible())
    win._toggle_sidebar(True)
    app.processEvents()
    check("sidebar restores", win.sidebar.isVisible())

    win._toggle_inspector(False)
    app.processEvents()
    check("inspector collapses", not win.inspector.isVisible())
    win._toggle_inspector(True)
    app.processEvents()
    check("inspector restores", win.inspector.isVisible())

    # -- telemetry -------------------------------------------------------------
    check("status bar reports counts", "2,0" in win.status_bar.left.text(),
          win.status_bar.left.text())
    check("status bar reports telemetry",
          "HTTPS" in win.status_bar.right.text()
          and "CORS" in win.status_bar.right.text()
          and "Qt" in win.status_bar.right.text(),
          win.status_bar.right.text())

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("Failed:")
        for name in FAIL:
            print(f"  - {name}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())