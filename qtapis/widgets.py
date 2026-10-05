"""Reusable chrome widgets: title bar, category tree, status bar, search well."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import theme

ALL_APIS = "__all__"
FAVORITES = "__favorites__"


class Logo(QWidget):
    """The 16x16 Qt mark: a cyan bracketed node."""

    def __init__(self, size: int = 16, parent=None):
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)

    def paintEvent(self, event):
        from PySide6.QtCore import QPointF, QRectF
        from PySide6.QtGui import QColor, QPainterPath

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        s = self._size
        c = QColor(theme.PRIMARY)

        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawRoundedRect(QRectF(0, s * 0.18, s * 0.22, s * 0.64), 1, 1)
        p.drawRoundedRect(QRectF(s * 0.78, s * 0.18, s * 0.22, s * 0.64), 1, 1)

        p.setBrush(QColor(theme.PRIMARY_CONTAINER))
        p.drawEllipse(QPointF(s / 2, s / 2), s * 0.17, s * 0.17)

        p.setPen(c)
        path = QPainterPath()
        path.moveTo(s * 0.22, s * 0.38)
        path.lineTo(s * 0.40, s * 0.42)
        path.moveTo(s * 0.22, s * 0.62)
        path.lineTo(s * 0.40, s * 0.58)
        path.moveTo(s * 0.78, s * 0.38)
        path.lineTo(s * 0.60, s * 0.42)
        path.moveTo(s * 0.78, s * 0.62)
        path.lineTo(s * 0.60, s * 0.58)
        p.drawPath(path)
        p.end()


class TitleBar(QWidget):
    minimizeRequested = Signal()
    maximizeRequested = Signal()
    closeRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("titleBar")
        self.setFixedHeight(theme.TITLEBAR_H)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 0, 0)
        layout.setSpacing(6)

        layout.addWidget(Logo(16))

        self.title = QLabel("Qt Public APIs Explorer")
        self.title.setObjectName("titleBarLabel")
        layout.addWidget(self.title)

        self.version = QLabel("— v2.4 (Qt 6.6)")
        self.version.setObjectName("titleBarVersion")
        layout.addWidget(self.version)

        layout.addStretch(1)

        self.avatar = QLabel("Q")
        self.avatar.setObjectName("avatar")
        self.avatar.setFixedSize(28, 28)
        self.avatar.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.avatar)
        layout.addSpacing(4)

        for obj, glyph, slot in (
            ("winMin", "─", self.minimizeRequested),
            ("winMax", "□", self.maximizeRequested),
            ("winClose", "✕", self.closeRequested),
        ):
            btn = QPushButton(glyph)
            btn.setObjectName(obj)
            btn.setFixedSize(44, theme.TITLEBAR_H)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(slot)
            layout.addWidget(btn)

    def set_version(self, text: str) -> None:
        self.version.setText(text)


class SearchWell(QWidget):
    """The 320px sunken search field with a leading glyph and clear button."""

    textChanged = Signal(str)
    clearRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("searchWell")
        self.setFixedHeight(28)
        self.setFixedWidth(320)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 4, 0)
        layout.setSpacing(6)

        glyph = QLabel("⌕")
        glyph.setStyleSheet(
            f"color: {theme.OUTLINE}; font-size: 13pt; background: transparent;"
        )
        layout.addWidget(glyph)

        self.input = QLineEdit()
        self.input.setObjectName("searchInput")
        self.input.setPlaceholderText(
            "Filter APIs (Name, Description, Auth)..."
        )
        self.input.setFrame(False)
        self.input.textChanged.connect(self.textChanged)
        layout.addWidget(self.input, 1)

        self.clear = QToolButton()
        self.clear.setObjectName("searchClear")
        self.clear.setText("✕")
        self.clear.setCursor(Qt.PointingHandCursor)
        self.clear.setVisible(False)
        self.clear.clicked.connect(self._on_clear)
        layout.addWidget(self.clear)

        self.hint = QLabel("Ctrl+K")
        self.hint.setObjectName("searchHint")
        layout.addWidget(self.hint)

        self.input.textChanged.connect(
            lambda t: self.clear.setVisible(bool(t))
        )

    def _on_clear(self) -> None:
        self.input.clear()
        self.input.setFocus()
        self.clearRequested.emit()

    def text(self) -> str:
        return self.input.text()

    def setText(self, text: str) -> None:
        self.input.setText(text)

    def focus_search(self) -> None:
        self.input.setFocus()
        self.input.selectAll()


class CategoryTree(QTreeWidget):
    """Sidebar tree: All APIs, Favorites, then each catalog category."""

    categorySelected = Signal(str)  # ALL_APIS / FAVORITES / category name

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(2)
        self.setHeaderHidden(True)
        self.setIndentation(14)
        self.setAnimated(False)
        self.setRootIsDecorated(False)
        self.setExpandsOnDoubleClick(False)
        self.setSelectionMode(QTreeWidget.SingleSelection)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setUniformRowHeights(True)
        header = self.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.resizeSection(1, 46)
        self.itemClicked.connect(self._on_clicked)

    def _on_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        self.categorySelected.emit(item.data(0, Qt.UserRole))

    def populate(self, counts: dict[str, int], total: int, favorites: int) -> None:
        self.clear()
        for key, label, glyph, count, color in (
            (ALL_APIS, "All APIs", "▤", total, theme.PRIMARY),
            (FAVORITES, "Favorites", "★", favorites, theme.AMBER),
        ):
            item = QTreeWidgetItem([label, ""])
            item.setData(0, Qt.UserRole, key)
            item.setIcon(0, _tree_icon(glyph, color))
            self.addTopLevelItem(item)
            _attach_count(item, count)

        for name in sorted(counts, key=str.lower):
            item = QTreeWidgetItem([name, ""])
            item.setData(0, Qt.UserRole, name)
            item.setIcon(0, _tree_icon("▸", theme.OUTLINE))
            self.addTopLevelItem(item)
            _attach_count(item, counts[name])

        self.setCurrentItem(self.topLevelItem(0))

    def select_key(self, key: str) -> None:
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            if item.data(0, Qt.UserRole) == key:
                self.setCurrentItem(item)
                self.scrollToItem(item)
                return

    def refresh_favorites(self, count: int) -> None:
        item = self.topLevelItem(1)
        if item is not None:
            _attach_count(item, count)


def _tree_icon(glyph: str, color: str) -> QIcon:
    from PySide6.QtGui import QColor, QFont

    pix = QPixmap(14, 14)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    f = QFont(theme.sans_family())
    f.setPointSizeF(9.0)
    p.setFont(f)
    p.setPen(QColor(color))
    p.drawText(pix.rect(), Qt.AlignCenter, glyph)
    p.end()
    return QIcon(pix)


def _attach_count(item: QTreeWidgetItem, count: int) -> None:
    item.setText(1, f"{count:,}")
    font = QFont(theme.mono_family())
    font.setPointSizeF(8.0)
    item.setFont(1, font)
    item.setForeground(1, QColor(theme.TEXT_TERTIARY))
    item.setTextAlignment(1, int(Qt.AlignRight | Qt.AlignVCenter))


class SidebarFooter(QWidget):
    """The sync status strip at the bottom of the category drawer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebarFooter")
        self.setFixedHeight(48)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        row = QHBoxLayout()
        row.setSpacing(4)

        self.dot = QLabel()
        self.dot.setObjectName("statusDot")
        self.dot.setFixedSize(6, 6)
        row.addWidget(self.dot)

        self.text = QLabel("Loaded from bundle")
        self.text.setObjectName("syncText")
        row.addWidget(self.text, 1)

        self.meta = QLabel("v2.4 cache")
        self.meta.setObjectName("syncMeta")
        self.meta.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(self.meta)
        layout.addLayout(row)

    def set_status(self, text: str, meta: str, ok: bool = True) -> None:
        self.text.setText(text)
        self.meta.setText(meta)
        color = theme.SECONDARY if ok else theme.ERROR
        self.text.setStyleSheet(
            f"color: {color}; font-family: '{theme.mono_family()}';"
            f" font-size: 8pt; font-weight: 600; background: transparent;"
        )
        self.dot.setStyleSheet(
            f"border-radius: 3px; background: {color};"
        )


class StatusBar(QWidget):
    """Pinned 24px telemetry strip."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statusBar")
        self.setFixedHeight(theme.STATUSBAR_H)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(16)

        self.left = QLabel("Ready")
        self.left.setObjectName("statusLeft")
        layout.addWidget(self.left)
        layout.addStretch(1)
        self.right = QLabel("")
        self.right.setObjectName("statusRight")
        self.right.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.right)

    def set_counts(self, shown: int, total: int, filtered: bool) -> None:
        if filtered:
            self.left.setText(
                f"{shown:,} of {total:,} APIs  ·  filter active"
            )
        else:
            self.left.setText(f"{total:,} APIs loaded  ·  0 filtered")

    def set_telemetry(self, text: str) -> None:
        self.right.setText(text)


def dot_label(text: str, color: str) -> QWidget:
    """A small colored status dot followed by a caption."""
    box = QWidget()
    layout = QHBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(5)
    dot = QLabel()
    dot.setFixedSize(6, 6)
    dot.setStyleSheet(f"border-radius: 3px; background: {color};")
    layout.addWidget(dot)
    label = QLabel(text)
    label.setObjectName("statusLeft")
    layout.addWidget(label)
    return box
