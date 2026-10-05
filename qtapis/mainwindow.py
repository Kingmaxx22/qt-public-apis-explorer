"""Main window: title bar, menu bar, toolbar, three-pane splitter, status bar."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone

from PySide6.QtCore import QPoint, Qt, QTimer, QUrl, qVersion
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .cards import CardView
from .catalog import ApiRecord, Catalog
from .curlgen import build_curl
from .delegates import ApiDelegate
from .inspector import Inspector
from .models import (
    ApiFilterProxy,
    ApiTableModel,
    COL_ACTIONS,
    COL_AUTH,
    COL_CATEGORY,
    COL_CHECKBOX,
    COL_CORS,
    COL_DESCRIPTION,
    COL_FAVORITE,
    COL_HTTPS,
    COL_NAME,
    COLUMN_LABELS,
    RecordStore,
)
from .store import (
    CatalogError,
    load_catalog,
    save_snapshot,
)
from .sync import SyncController
from .widgets import (
    ALL_APIS,
    FAVORITES,
    CategoryTree,
    SearchWell,
    SidebarFooter,
    StatusBar,
    TitleBar,
    dot_label,
)

APP_VERSION = "2.4.1"

# Pointer distance from a window edge that starts a resize drag.
RESIZE_MARGIN = 6


def _friendly_age(stamp: str) -> str:
    """Render an ISO timestamp as a short 'synced N ago' string."""
    if not stamp:
        return "cache"
    try:
        when = datetime.fromisoformat(stamp)
    except ValueError:
        return stamp[:10]
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - when
    mins = int(delta.total_seconds() // 60)
    if mins < 1:
        return "just now"
    if mins < 60:
        return f"{mins}m ago"
    hours = mins // 60
    if hours < 24:
        return f"{hours}h ago"
    return f"{hours // 24}d ago"


class MainWindow(QMainWindow):
    def __init__(self, catalog: Catalog, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Qt Public APIs Explorer")
        # Frameless: the themed TitleBar is the only chrome. Leaving the native
        # frame on would stack two title bars.
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.resize(1440, 880)
        self.setMinimumSize(960, 600)

        # Frameless windows lose the native resize grip, so track the edges.
        self._resize_edge: str | None = None
        self._resize_origin: tuple[int, int, int, int] | None = None
        self._resize_global: QPoint | None = None
        self._hover_edge: str | None = None
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

        self.catalog = catalog
        self.store = RecordStore(catalog.records, catalog.fetched_at, self)
        self._selected_key = ALL_APIS
        self._sidebar_visible = True
        self._inspector_visible = True
        self._view_mode = "table"

        self.sync = SyncController(self)
        self.sync.progressed.connect(self._on_sync_progressed)
        self.sync.finished.connect(self._on_sync_finished)
        self.sync.failed.connect(self._on_sync_failed)

        self._build_ui()
        self._build_actions()
        self._apply_catalog(catalog)
        QTimer.singleShot(0, self.table_view.setFocus)

    # ------------------------------------------------------- window control

    def toggle_maximized(self) -> None:
        """Maximize / restore, keeping the glyph in sync."""
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        self.title_bar.set_maximized(self.isMaximized())

    def changeEvent(self, event):
        # The WM can maximize independently (double-click, snap, tiling WM).
        if event.type() == event.Type.WindowStateChange:
            self.title_bar.set_maximized(self.isMaximized())
        super().changeEvent(event)

    def _edge_at(self, pos: QPoint) -> str | None:
        """Which resize edge (if any) the global point sits on."""
        if self.isMaximized():
            return None
        frame = self.frameGeometry()
        margin = RESIZE_MARGIN
        left = pos.x() - frame.left()
        top = pos.y() - frame.top()
        right = frame.right() - pos.x()
        bottom = frame.bottom() - pos.y()

        on_left = 0 <= left <= margin
        on_right = 0 <= right <= margin
        on_top = 0 <= top <= margin
        on_bottom = 0 <= bottom <= margin
        if not (on_left or on_right or on_top or on_bottom):
            return None
        if on_top and on_left:
            return "top-left"
        if on_top and on_right:
            return "top-right"
        if on_bottom and on_left:
            return "bottom-left"
        if on_bottom and on_right:
            return "bottom-right"
        if on_left:
            return "left"
        if on_right:
            return "right"
        if on_top:
            return "top"
        return "bottom"

    _CURSORS = {
        "left": Qt.SizeHorCursor,
        "right": Qt.SizeHorCursor,
        "top": Qt.SizeVerCursor,
        "bottom": Qt.SizeVerCursor,
        "top-left": Qt.SizeFDiagCursor,
        "bottom-right": Qt.SizeFDiagCursor,
        "top-right": Qt.SizeBDiagCursor,
        "bottom-left": Qt.SizeBDiagCursor,
    }

    def eventFilter(self, watched, event):
        if self._resize_edge is not None and event.type() in (
            event.Type.MouseMove,
            event.Type.MouseButtonRelease,
        ):
            if event.type() == event.Type.MouseButtonRelease:
                self._end_resize()
                return False
            self._apply_resize(event.globalPosition().toPoint())
            return True

        if event.type() in (event.Type.MouseMove, event.Type.MouseButtonPress):
            pos = event.globalPosition().toPoint()
            if event.type() == event.Type.MouseButtonPress:
                edge = self._edge_at(pos)
                if edge:
                    self._resize_edge = edge
                    self._resize_origin = (
                        self.geometry().x(), self.geometry().y(),
                        self.width(), self.height(),
                    )
                    self._resize_global = pos
                    return True
                return False
            # Hover feedback only for this window. setOverrideCursor pushes onto
            # an override stack, so it must be balanced by a restore before
            # changing edge - otherwise the stack grows on every mouse move.
            if watched is self or (watched is not None
                                   and self.isAncestorOf(watched)):
                self._set_hover_cursor(self._edge_at(pos))
            return False
        return False

    def _set_hover_cursor(self, edge: str | None) -> None:
        """Set the resize cursor for `edge`, balancing the override stack."""
        if edge == self._hover_edge:
            return
        if self._hover_edge is not None:
            QApplication.restoreOverrideCursor()
        self._hover_edge = edge
        if edge is not None:
            QApplication.setOverrideCursor(self._CURSORS[edge])

    def _apply_resize(self, pos: QPoint) -> None:
        if self._resize_origin is None or self._resize_global is None:
            return
        x, y, w, h = self._resize_origin
        dx = pos.x() - self._resize_global.x()
        dy = pos.y() - self._resize_global.y()
        edge = self._resize_edge or ""

        if "left" in edge:
            x += dx
            w -= dx
        elif "right" in edge:
            w += dx
        if "top" in edge:
            y += dy
            h -= dy
        elif "bottom" in edge:
            h += dy

        # Clamp to the minimum size by absorbing the overflow on the far edge.
        if w < self.minimumWidth():
            if "left" in edge:
                x -= self.minimumWidth() - w
            w = self.minimumWidth()
        if h < self.minimumHeight():
            if "top" in edge:
                y -= self.minimumHeight() - h
            h = self.minimumHeight()

        self.setGeometry(x, y, w, h)

    def _end_resize(self) -> None:
        self._resize_edge = None
        self._resize_origin = None
        self._resize_global = None
        if self._hover_edge is not None:
            QApplication.restoreOverrideCursor()
            self._hover_edge = None

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.title_bar = TitleBar()
        self.title_bar.minimizeRequested.connect(self.showMinimized)
        self.title_bar.maximizeRequested.connect(self.toggle_maximized)
        self.title_bar.closeRequested.connect(self.close)
        root.addWidget(self.title_bar)

        root.addWidget(self._build_menubar())
        root.addWidget(self._build_toolbar())

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(1)

        self.sidebar = self._build_sidebar()
        self.splitter.addWidget(self.sidebar)

        self.splitter.addWidget(self._build_workspace())

        self.inspector = Inspector()
        self.splitter.addWidget(self.inspector)

        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.splitter.setSizes([theme.SIDEBAR_W, 800, theme.INSPECTOR_W])
        root.addWidget(self.splitter, 1)

        self.status_bar = StatusBar()
        root.addWidget(self.status_bar)

    def _build_menubar(self) -> QWidget:
        from PySide6.QtWidgets import QMenuBar

        bar = QMenuBar()
        bar.setObjectName("menuBar")
        bar.setFixedHeight(theme.MENUBAR_H)
        self._menu_bar = bar
        return bar

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("toolbar")
        bar.setFixedHeight(theme.TOOLBAR_H)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(8)

        self.search = SearchWell()
        self.search.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search)

        self.auth_combo = QComboBox()
        self.auth_combo.setFixedWidth(120)
        self.auth_combo.addItems(["Auth: All", "Auth: None", "Auth: API Key", "Auth: OAuth"])
        self.auth_combo.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self.auth_combo)

        self.https_btn = QToolButton()
        self.https_btn.setObjectName("toolButtonAccent")
        self.https_btn.setText("🔒 HTTPS")
        self.https_btn.setCheckable(True)
        self.https_btn.setToolTip("Show only HTTPS-enabled endpoints")
        self.https_btn.setCursor(Qt.PointingHandCursor)
        self.https_btn.toggled.connect(self._on_filter_changed)
        layout.addWidget(self.https_btn)

        self.cors_combo = QComboBox()
        self.cors_combo.setFixedWidth(124)
        self.cors_combo.addItems(["CORS: ANY", "CORS: YES", "CORS: NO"])
        self.cors_combo.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self.cors_combo)

        layout.addStretch(1)

        self.sync_btn = QToolButton()
        self.sync_btn.setObjectName("toolButton")
        self.sync_btn.setText("⟳ Sync")
        self.sync_btn.setCursor(Qt.PointingHandCursor)
        self.sync_btn.clicked.connect(self.refresh_catalog)
        layout.addWidget(self.sync_btn)

        self.export_btn = QToolButton()
        self.export_btn.setObjectName("toolButton")
        self.export_btn.setText("⭳ Export")
        self.export_btn.setCursor(Qt.PointingHandCursor)
        self.export_btn.clicked.connect(self.export_catalog)
        layout.addWidget(self.export_btn)

        self.sidebar_btn = QToolButton()
        self.sidebar_btn.setObjectName("toolButton")
        self.sidebar_btn.setText("▤")
        self.sidebar_btn.setToolTip("Toggle the category drawer (Ctrl+B)")
        self.sidebar_btn.setCheckable(True)
        self.sidebar_btn.setChecked(True)
        self.sidebar_btn.setCursor(Qt.PointingHandCursor)
        self.sidebar_btn.toggled.connect(self._toggle_sidebar)
        layout.addWidget(self.sidebar_btn)

        # View switcher, mirroring the mock's segmented control.
        segmented = QWidget()
        segmented.setObjectName("segmented")
        seg_layout = QHBoxLayout(segmented)
        seg_layout.setContentsMargins(2, 2, 2, 2)
        seg_layout.setSpacing(2)
        self.view_buttons: dict[str, QToolButton] = {}
        for mode, glyph, tip in (
            ("table", "▤", "Table view"),
            ("cards", "▦", "Card view"),
        ):
            btn = QToolButton()
            btn.setText(glyph)
            btn.setToolTip(tip)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _c, m=mode: self.set_view_mode(m))
            seg_layout.addWidget(btn)
            self.view_buttons[mode] = btn
        self.view_buttons["table"].setChecked(True)
        layout.addWidget(segmented)
        return bar

    def _build_sidebar(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("sidebar")
        panel.setMinimumWidth(theme.SIDEBAR_MIN_W)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("sidebarHeader")
        header.setFixedHeight(28)
        hlayout = QHBoxLayout(header)
        hlayout.setContentsMargins(12, 0, 6, 0)
        title = QLabel("CATEGORIES TREE")
        title.setObjectName("sidebarHeaderLabel")
        hlayout.addWidget(title)
        hlayout.addStretch(1)
        collapse = QToolButton()
        collapse.setObjectName("sidebarCollapse")
        collapse.setText("⇔")
        collapse.setCursor(Qt.PointingHandCursor)
        collapse.clicked.connect(self._toggle_sidebar)
        hlayout.addWidget(collapse)
        layout.addWidget(header)

        self.tree = CategoryTree()
        self.tree.categorySelected.connect(self._on_category_selected)
        layout.addWidget(self.tree, 1)

        self.sidebar_footer = SidebarFooter()
        layout.addWidget(self.sidebar_footer)
        return panel

    def _build_workspace(self) -> QWidget:
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_subheader())

        self.table_view = QTableView()
        self.model = ApiTableModel(self.store, self)
        self.proxy = ApiFilterProxy(self)
        self.proxy.setSourceModel(self.model)
        self.table_view.setModel(self.proxy)

        self.delegate = ApiDelegate(self.table_view)
        self.delegate.actionClicked.connect(self._on_action_clicked)
        self.delegate.favoriteClicked.connect(self._on_favorite_clicked)
        self.table_view.setItemDelegate(self.delegate)

        self.table_view.setAlternatingRowColors(True)
        self.table_view.setShowGrid(False)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_view.setSortingEnabled(True)
        self.table_view.setWordWrap(False)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.verticalHeader().setDefaultSectionSize(theme.TABLE_ROW_H)
        self.table_view.verticalHeader().setMinimumSectionSize(theme.TABLE_ROW_H)
        self.table_view.horizontalHeader().setFixedHeight(theme.HEADER_H)
        self.table_view.horizontalHeader().setHighlightSections(False)
        self.table_view.horizontalHeader().setSectionsClickable(True)
        self.table_view.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table_view.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self._configure_columns()
        self.table_view.sortByColumn(COL_NAME, Qt.AscendingOrder)

        self.table_view.selectionModel().selectionChanged.connect(
            self._on_selection_changed
        )
        self.table_view.doubleClicked.connect(self._on_row_activated)
        layout.addWidget(self.table_view, 1)

        self.card_view = CardView()
        self.card_view.cardActivated.connect(self._on_card_activated)
        self.card_view.pageChanged.connect(self._on_card_page_changed)
        self.card_view.setVisible(False)
        layout.addWidget(self.card_view, 1)
        return pane

    def _build_subheader(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("subheader")
        bar.setFixedHeight(28)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(8)

        icon = QLabel("≡")
        icon.setStyleSheet(
            f"color: {theme.PRIMARY}; font-size: 12pt; background: transparent;"
        )
        layout.addWidget(icon)

        self.view_label = QLabel("View: Active Public Registry")
        self.view_label.setObjectName("subheaderText")
        layout.addWidget(self.view_label)

        layout.addWidget(_pipe())
        layout.addWidget(dot_label("Registry live", theme.SECONDARY))
        layout.addWidget(_pipe())
        self.sorted_label = QLabel("Sorted by: API Name (Asc)")
        self.sorted_label.setObjectName("subheaderMeta")
        layout.addWidget(self.sorted_label)

        layout.addStretch(1)

        self.columns_btn = QToolButton()
        self.columns_btn.setObjectName("miniButton")
        self.columns_btn.setText("Columns (9/9)")
        self.columns_btn.setEnabled(False)
        self.columns_btn.setCursor(Qt.PointingHandCursor)
        self.columns_btn.clicked.connect(self._cycle_columns)
        layout.addWidget(self.columns_btn)

        self.fit_btn = QToolButton()
        self.fit_btn.setObjectName("miniButton")
        self.fit_btn.setText("Fit")
        self.fit_btn.setEnabled(False)
        self.fit_btn.setCursor(Qt.PointingHandCursor)
        self.fit_btn.clicked.connect(self.fit_columns)
        layout.addWidget(self.fit_btn)

        self.card_caption = QLabel("")
        self.card_caption.setObjectName("subheaderMeta")
        self.card_caption.setVisible(False)
        layout.addWidget(self.card_caption)
        return bar

    def _configure_columns(self) -> None:
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(COL_CHECKBOX, QHeaderView.Fixed)
        header.setSectionResizeMode(COL_FAVORITE, QHeaderView.Fixed)
        header.setSectionResizeMode(COL_NAME, QHeaderView.Interactive)
        header.setSectionResizeMode(COL_DESCRIPTION, QHeaderView.Stretch)
        header.setSectionResizeMode(COL_AUTH, QHeaderView.Fixed)
        header.setSectionResizeMode(COL_HTTPS, QHeaderView.Fixed)
        header.setSectionResizeMode(COL_CORS, QHeaderView.Fixed)
        header.setSectionResizeMode(COL_CATEGORY, QHeaderView.Interactive)
        header.setSectionResizeMode(COL_ACTIONS, QHeaderView.Fixed)
        for col, width in (
            (COL_CHECKBOX, 30),
            (COL_FAVORITE, 28),
            (COL_NAME, 190),
            (COL_AUTH, 92),
            (COL_HTTPS, 60),
            (COL_CORS, 72),
            (COL_CATEGORY, 132),
            (COL_ACTIONS, 84),
        ):
            self.table_view.setColumnWidth(col, width)
        self.table_view.setColumnWidth(COL_DESCRIPTION, 300)
        header.sectionResized.connect(self._update_columns_button)
        header.sortIndicatorChanged.connect(
            lambda section, order: self._update_sort_label(section, order)
        )
        self._update_sort_label(COL_NAME, Qt.AscendingOrder)

    def fit_columns(self) -> None:
        self.table_view.resizeColumnsToContents()
        for col, width in (
            (COL_CHECKBOX, 30),
            (COL_FAVORITE, 28),
            (COL_NAME, 190),
            (COL_AUTH, 92),
            (COL_HTTPS, 60),
            (COL_CORS, 72),
            (COL_CATEGORY, 132),
            (COL_ACTIONS, 84),
        ):
            self.table_view.setColumnWidth(col, width)

    def _update_sort_label(self, section: int, order) -> None:
        labels = {c: l for c, l in enumerate(COLUMN_LABELS)}
        name = labels.get(section, "Column")
        direction = "Desc" if order == Qt.DescendingOrder else "Asc"
        self.sorted_label.setText(f"Sorted by: {name} ({direction})")

    # -------------------------------------------------------------- actions

    def _build_actions(self) -> None:
        bar = self._menu_bar

        file_menu = bar.addMenu("File")
        act_sync = QAction("⟳  Sync from GitHub", self)
        act_sync.setShortcut(QKeySequence("Ctrl+R"))
        act_sync.triggered.connect(self.refresh_catalog)
        self.sync_menu_action = act_sync
        file_menu.addAction(act_sync)

        act_export = QAction("⭳  Export visible as CSV…", self)
        act_export.setShortcut(QKeySequence("Ctrl+E"))
        act_export.triggered.connect(self.export_catalog)
        file_menu.addAction(act_export)
        file_menu.addSeparator()

        act_quit = QAction("✕  Quit", self)
        act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        edit_menu = bar.addMenu("Edit")
        act_find = QAction("⌕  Find APIs", self)
        act_find.setShortcut(QKeySequence("Ctrl+K"))
        act_find.setShortcutContext(Qt.WindowShortcut)
        act_find.triggered.connect(self.search.focus_search)
        edit_menu.addAction(act_find)

        act_fav = QAction("★  Toggle favorite", self)
        act_fav.setShortcut(QKeySequence("Ctrl+D"))
        act_fav.triggered.connect(self._toggle_selected_favorite)
        edit_menu.addAction(act_fav)
        edit_menu.addSeparator()
        act_copy = QAction("⧉  Copy cURL", self)
        act_copy.setShortcut(QKeySequence("Ctrl+Shift+C"))
        act_copy.triggered.connect(self._copy_selected_curl)
        edit_menu.addAction(act_copy)
        act_open = QAction("↗  Open documentation", self)
        act_open.setShortcut(QKeySequence("Ctrl+Return"))
        act_open.triggered.connect(self._open_selected)
        edit_menu.addAction(act_open)

        view_menu = bar.addMenu("View")
        self.act_sidebar = QAction("▤  Category drawer", self)
        self.act_sidebar.setCheckable(True)
        self.act_sidebar.setChecked(True)
        self.act_sidebar.setShortcut(QKeySequence("Ctrl+B"))
        self.act_sidebar.triggered.connect(self._toggle_sidebar)
        view_menu.addAction(self.act_sidebar)

        self.act_inspector = QAction("▦  Detail inspector", self)
        self.act_inspector.setCheckable(True)
        self.act_inspector.setChecked(True)
        self.act_inspector.setShortcut(QKeySequence("Ctrl+I"))
        self.act_inspector.triggered.connect(self._toggle_inspector)
        view_menu.addAction(self.act_inspector)
        view_menu.addSeparator()

        self.act_card_view = QAction("▦  Card view", self)
        self.act_card_view.setCheckable(True)
        self.act_card_view.setShortcut(QKeySequence("Ctrl+Shift+V"))
        self.act_card_view.triggered.connect(
            lambda checked: self.set_view_mode("cards" if checked else "table")
        )
        view_menu.addAction(self.act_card_view)
        view_menu.addSeparator()

        act_fit = QAction("↔  Fit columns", self)
        act_fit.triggered.connect(self.fit_columns)
        view_menu.addAction(act_fit)

        act_reset = QAction("⟲  Reset filters", self)
        act_reset.setShortcut(QKeySequence("Ctrl+Shift+R"))
        act_reset.triggered.connect(self.reset_filters)
        view_menu.addAction(act_reset)

        tools_menu = bar.addMenu("Tools")
        act_copy_all = QAction("⧉  Copy all visible cURLs", self)
        act_copy_all.triggered.connect(self._copy_all_curl)
        tools_menu.addAction(act_copy_all)

        help_menu = bar.addMenu("Help")
        act_about = QAction("ℹ  About", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)
        act_source = QAction("↗  Open upstream repository", self)
        act_source.triggered.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://github.com/public-apis/public-apis")
            )
        )
        help_menu.addAction(act_source)

    # --------------------------------------------------------------- catalog

    def _apply_catalog(self, catalog: Catalog) -> None:
        self.catalog = catalog
        self.store.records = list(catalog.records)
        self.store.fetched_at = catalog.fetched_at
        self.model._on_catalog_replaced()
        self.tree.populate(
            self.store.category_counts(), len(catalog.records),
            self.store.favorite_count(),
        )
        self.tree.select_key(self._selected_key)
        self.title_bar.set_version(f"— v{APP_VERSION} (Qt {qVersion()})")
        self.sidebar_footer.set_status(
            f"Synced {_friendly_age(catalog.fetched_at)}" if catalog.fetched_at
            else "Bundled snapshot",
            f"v{APP_VERSION} cache",
        )
        self._update_status()

    def refresh_catalog(self) -> bool:
        """Kick off a refresh on a worker thread; the UI stays live."""
        if not self.sync.start():
            self.statusBar().showMessage("A sync is already running", 2500)
            return False
        self.sync_btn.setEnabled(False)
        self.sync_menu_action.setEnabled(False)
        return True

    def _on_sync_progressed(self, message: str) -> None:
        self.sidebar_footer.set_status(message, "fetching", ok=False)

    def _on_sync_finished(self, catalog) -> None:
        self.sync_btn.setEnabled(True)
        self.sync_menu_action.setEnabled(True)
        self._apply_catalog(catalog)
        self.statusBar().showMessage(
            f"Synced {len(catalog.records):,} APIs from GitHub", 4000
        )

    def _on_sync_failed(self, message: str) -> None:
        self.sync_btn.setEnabled(True)
        self.sync_menu_action.setEnabled(True)
        self.sidebar_footer.set_status("Sync failed", "offline", ok=False)
        QMessageBox.warning(self, "Sync failed", message)

    def export_catalog(self) -> None:
        records = self._visible_records()
        if not records:
            self.statusBar().showMessage("Nothing to export", 3000)
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export visible APIs",
            "public-apis.csv",
            "CSV files (*.csv);;JSON files (*.json)",
        )
        if not path:
            return
        try:
            if path.lower().endswith(".json"):
                payload = [r.to_dict() for r in records]
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(payload, fh, indent=1, ensure_ascii=False)
            else:
                with open(path, "w", encoding="utf-8", newline="") as fh:
                    writer = csv.writer(fh)
                    writer.writerow(
                        ["Name", "Description", "Auth", "HTTPS", "CORS",
                         "Category", "URL"]
                    )
                    for r in records:
                        writer.writerow(
                            [r.name, r.description, r.auth, r.https, r.cors,
                             r.category, r.url]
                        )
        except OSError as exc:
            QMessageBox.warning(self, "Export failed", str(exc))
            return
        self.statusBar().showMessage(f"Exported {len(records):,} rows to {path}", 5000)

    # --------------------------------------------------------------- filters

    def _on_search_changed(self, text: str) -> None:
        self.proxy.set_query(text)
        self._update_status()

    def _on_filter_changed(self) -> None:
        self.proxy.auth = ["all", "none", "apikey", "oauth"][self.auth_combo.currentIndex()]
        self.proxy.https = "yes" if self.https_btn.isChecked() else "any"
        self.proxy.cors = ["any", "yes", "no"][self.cors_combo.currentIndex()]
        self.proxy.invalidateFilter()
        self._update_status()

    def reset_filters(self) -> None:
        self.search.setText("")
        self.auth_combo.setCurrentIndex(0)
        self.https_btn.setChecked(False)
        self.cors_combo.setCurrentIndex(0)
        self.proxy.category = None
        self.proxy.favorites_only = False
        self._selected_key = ALL_APIS
        self.tree.select_key(ALL_APIS)
        self.proxy.invalidateFilter()
        self._update_status()
        self.statusBar().showMessage("Filters reset", 2500)

    def _on_category_selected(self, key: str) -> None:
        self._selected_key = key
        self.proxy.favorites_only = key == FAVORITES
        self.proxy.category = None if key in (ALL_APIS, FAVORITES) else key
        self.proxy.invalidateFilter()
        self.table_view.clearSelection()
        self.inspector.set_record(None)
        label = "Favorites" if key == FAVORITES else ("Active Public Registry" if key == ALL_APIS else key)
        self.view_label.setText(f"View: {label}")
        self._update_status()

    def _toggle_sidebar(self, visible: bool) -> None:
        self._sidebar_visible = visible
        self.sidebar.setVisible(visible)
        self.sidebar_btn.setChecked(visible)
        self.act_sidebar.setChecked(visible)
        sizes = self.splitter.sizes()
        if visible:
            if sizes[0] <= 0:
                self.splitter.setSizes([theme.SIDEBAR_W, sizes[1], sizes[2]])
        else:
            self.splitter.setSizes([0, sizes[1], sizes[2]])

    def _toggle_inspector(self, visible: bool) -> None:
        self._inspector_visible = visible
        self.inspector.setVisible(visible)
        self.act_inspector.setChecked(visible)
        sizes = self.splitter.sizes()
        if visible and sizes[2] <= 0:
            self.splitter.setSizes([sizes[0], sizes[1], theme.INSPECTOR_W])
        else:
            self.splitter.setSizes([sizes[0], sizes[1], 0])

    def set_view_mode(self, mode: str) -> None:
        """Switch between the table grid and the card grid."""
        if mode not in ("table", "cards"):
            return
        self._view_mode = mode
        self.table_view.setVisible(mode == "table")
        self.card_view.setVisible(mode == "cards")
        self.card_caption.setVisible(mode == "cards")
        self.columns_btn.setEnabled(mode == "table")
        self.fit_btn.setEnabled(mode == "table")
        for name, btn in self.view_buttons.items():
            btn.setChecked(name == mode)
        self.act_card_view.setChecked(mode == "cards")
        if mode == "cards":
            self._refresh_cards()

    def _refresh_cards(self) -> None:
        """Rebuild the card page from the current filtered records."""
        if self._view_mode != "cards":
            return
        records = self._visible_records()
        self.card_view.set_records(records)
        pages = self.card_view.page_count()
        self.card_caption.setText(
            f"{pages:,} page{'s' if pages != 1 else ''}  ·  {len(records):,} cards"
        )
        self.card_caption.setVisible(True)

    def _on_card_page_changed(self, page: int) -> None:
        """Keep the subheader caption in step with the pager."""
        if self._view_mode != "cards":
            return
        self.card_caption.setText(
            f"Page {page:,} of {self.card_view.page_count():,}"
        )

    def _on_card_activated(self, record: ApiRecord) -> None:
        self.inspector.set_record(record)
        if not self._inspector_visible:
            self._toggle_inspector(True)

    def _cycle_columns(self) -> None:
        header = self.table_view.horizontalHeader()
        hidden = not header.isSectionHidden(COL_DESCRIPTION)
        header.setSectionHidden(COL_DESCRIPTION, hidden)
        self._update_columns_button()

    def _update_columns_button(self, *_args) -> None:
        header = self.table_view.horizontalHeader()
        total = header.count()
        visible = sum(
            1 for c in range(total) if not header.isSectionHidden(c)
        )
        self.columns_btn.setText(f"Columns ({visible}/{total})")

    # ------------------------------------------------------------- selection

    def _selected_record(self) -> ApiRecord | None:
        indexes = self.table_view.selectionModel().selectedRows()
        if not indexes:
            return None
        return indexes[0].data(Qt.UserRole)

    def _on_selection_changed(self, *_args) -> None:
        record = self._selected_record()
        self.inspector.set_record(record)
        if record is None:
            return
        # Reveal the owning category in the tree so context is never lost.
        if self._selected_key == ALL_APIS and self.proxy.category is None:
            pass

    def _on_row_activated(self, index) -> None:
        record = index.data(Qt.UserRole)
        if record is None:
            return
        if not self._inspector_visible:
            self._toggle_inspector(True)
        else:
            self.inspector.set_record(record)

    def _on_action_clicked(self, index, code: int) -> None:
        record = index.data(Qt.UserRole)
        if record is None:
            return
        if code == ApiDelegate.ACTION_COPY:
            QApplication.clipboard().setText(build_curl(record))
            self.statusBar().showMessage(f"Copied cURL for {record.name}", 3000)
        elif code == ApiDelegate.ACTION_INSPECT:
            self.inspector.set_record(record)
            if not self._inspector_visible:
                self._toggle_inspector(True)
        elif code == ApiDelegate.ACTION_PING:
            QDesktopServices.openUrl(QUrl(record.url))

    def _on_favorite_clicked(self, index) -> None:
        record = index.data(Qt.UserRole)
        if record is not None:
            self.store.toggle_favorite(record)
            self.tree.refresh_favorites(self.store.favorite_count())
            self._update_status()
            self.statusBar().showMessage(
                f"{'Added' if record.favorite else 'Removed'} "
                f"{record.name} {'to' if record.favorite else 'from'} favorites",
                2500,
            )

    def _toggle_selected_favorite(self) -> None:
        record = self._selected_record()
        if record is None:
            return
        self.store.toggle_favorite(record)
        self.tree.refresh_favorites(self.store.favorite_count())
        self.inspector.set_record(record)
        self._update_status()

    def _copy_selected_curl(self) -> None:
        record = self._selected_record()
        if record is None:
            return
        QApplication.clipboard().setText(build_curl(record))
        self.statusBar().showMessage(f"Copied cURL for {record.name}", 3000)

    def _copy_all_curl(self) -> None:
        records = self._visible_records()
        if not records:
            return
        QApplication.clipboard().setText(
            "\n".join(build_curl(r) for r in records)
        )
        self.statusBar().showMessage(
            f"Copied {len(records):,} cURL commands", 3000
        )

    def _open_selected(self) -> None:
        record = self._selected_record()
        if record is not None and record.url:
            QDesktopServices.openUrl(QUrl(record.url))

    # ---------------------------------------------------------------- status

    def _visible_records(self) -> list[ApiRecord]:
        out = []
        for row in range(self.proxy.rowCount()):
            out.append(self.proxy.index(row, 0).data(Qt.UserRole))
        return out

    def _update_status(self) -> None:
        shown = self.proxy.rowCount()
        total = len(self.store.records)
        filtered = bool(
            self.proxy.query
            or self.proxy.auth != "all"
            or self.proxy.https != "any"
            or self.proxy.cors != "any"
            or self.proxy.category
            or self.proxy.favorites_only
        )
        self.status_bar.set_counts(shown, total, filtered)

        records = self.store.records
        https_pct = (
            round(100 * sum(1 for r in records if r.is_https) / len(records))
            if records else 0
        )
        cors_pct = (
            round(100 * sum(1 for r in records if r.cors == "yes") / len(records))
            if records else 0
        )
        self.status_bar.set_telemetry(
            f"HTTPS {https_pct}%  ·  CORS {cors_pct}%  ·  Qt {qVersion()}"
        )
        self._refresh_cards()

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Qt Public APIs Explorer",
            f"<b>Qt Public APIs Explorer v{APP_VERSION}</b><br><br>"
            "A desktop browser for the community-curated "
            "<a href='https://github.com/public-apis/public-apis'>public-apis</a> "
            "registry.<br><br>"
            f"{len(self.store.records):,} APIs across "
            f"{len(self.store.category_counts())} categories.<br>"
            "Built with PySide6 (Qt 6).",
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        self._end_resize()
        self.title_bar.set_maximized(False)
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        # Never leave a QThread running at teardown.
        self.sync.shutdown()
        # Persist favorites so they survive a restart.
        try:
            save_snapshot(Catalog(self.store.records, self.store.fetched_at))
        except OSError:
            pass
        super().closeEvent(event)


def _pipe() -> QLabel:
    label = QLabel("│")
    label.setStyleSheet(
        f"color: {theme.OUTLINE_VARIANT}; font-size: 9pt;"
        " background: transparent;"
    )
    return label


def launch() -> int:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Qt Public APIs Explorer")
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("FreeApi")

    try:
        catalog = load_catalog()
    except CatalogError as exc:
        QMessageBox.critical(
            None, "Catalog unavailable",
            f"Could not load the API catalog.\n\n{exc}",
        )
        return 1

    window = MainWindow(catalog)
    window.show()
    return app.exec()