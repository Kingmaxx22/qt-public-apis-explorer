"""Item delegates that paint the design's status chips and inline actions."""

from __future__ import annotations

import math

from PySide6.QtCore import QModelIndex, QPointF, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPolygonF
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

from . import theme
from .models import (
    COL_ACTIONS,
    COL_AUTH,
    COL_CHECKBOX,
    COL_CATEGORY,
    COL_CORS,
    COL_FAVORITE,
    COL_HTTPS,
    COL_NAME,
)

# (text, text color, border color, background color)
AUTH_STYLES = {
    "none": ("NO AUTH", theme.SECONDARY, theme.SECONDARY, theme.SECONDARY),
    "apikey": ("API KEY", theme.AMBER, theme.AMBER, theme.AMBER),
    "oauth": ("OAUTH", theme.TERTIARY, theme.TERTIARY, theme.TERTIARY),
}

_FLAG_STYLES = {
    "yes": (theme.SECONDARY, theme.SECONDARY),
    "no": (theme.ERROR, theme.ERROR),
    "unknown": (theme.ON_SURFACE_VARIANT, theme.OUTLINE),
}


def _with_alpha(color: QColor, a: float) -> QColor:
    c = QColor(color)
    c.setAlphaF(a)
    return c


class _ChipMixin:
    """Shared chip-painting helper."""

    def _paint_chip(self, painter: QPainter, rect: QRect, text, fg: str,
                    border: str, bg: str) -> None:
        if not text:
            return
        f = QFont(theme.mono_family())
        f.setPointSizeF(8.0)
        f.setWeight(QFont.DemiBold)
        painter.setFont(f)
        fm = painter.fontMetrics()
        chip_w = min(rect.width(), fm.horizontalAdvance(str(text)) + 12)
        chip = QRect(0, 0, chip_w, 20)
        x = rect.x() + (rect.width() - chip_w) // 2
        chip.moveLeft(x)
        chip.moveTop(rect.y() + (rect.height() - 20) // 2)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(chip, 2, 2)
        painter.fillPath(path, _with_alpha(QColor(bg), 0.14))
        painter.setPen(QColor(border) if QColor(border).isValid() else QColor(theme.OUTLINE))
        painter.drawPath(path)
        painter.setPen(QColor(fg))
        painter.drawText(chip, Qt.AlignCenter, str(text))
        painter.restore()


class ApiDelegate(_ChipMixin, QStyledItemDelegate):
    """Paints every column of the API grid."""

    actionClicked = Signal(QModelIndex, int)  # index, action code
    favoriteClicked = Signal(QModelIndex)

    ACTION_PING = 0
    ACTION_COPY = 1
    ACTION_INSPECT = 2

    def sizeHint(self, option, index) -> QSize:
        size = super().sizeHint(option, index)
        return QSize(size.width(), theme.TABLE_ROW_H)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        record = index.data(Qt.UserRole)
        if record is None:
            super().paint(painter, option, index)
            return

        col = index.column()
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Selection / hover background.
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)
        bg = None
        if selected:
            bg = QColor(theme.SELECTION)
        elif hovered:
            bg = _with_alpha(QColor(theme.SURFACE_BRIGHT), 0.45)
        if bg is not None:
            painter.fillRect(option.rect, bg)
        if selected:
            painter.setPen(QColor(theme.PRIMARY_CONTAINER))
            painter.drawLine(option.rect.topLeft(), option.rect.topRight())
            painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
        painter.setPen(Qt.NoPen)
        painter.restore()

        if col == COL_CHECKBOX:
            self._paint_checkbox(painter, option.rect, bool(option.state & QStyle.State_Selected))
        elif col == COL_FAVORITE:
            self._paint_star(painter, option.rect, record.favorite,
                             bool(option.state & QStyle.State_MouseOver))
        elif col == COL_NAME:
            self._paint_name(painter, option, record)
        elif col == COL_AUTH:
            self._paint_auth(painter, option.rect, record.auth)
        elif col == COL_HTTPS:
            self._paint_flag(painter, option.rect, record.https)
        elif col == COL_CORS:
            self._paint_cors(painter, option.rect, record.cors)
        elif col == COL_CATEGORY:
            self._paint_category(painter, option.rect, record.category)
        elif col == COL_ACTIONS:
            self._paint_actions(painter, option.rect,
                                bool(option.state & QStyle.State_MouseOver))
        else:
            self._paint_text(painter, option, index,
                             theme.ON_SURFACE_VARIANT, theme.sans_family(), 9.5)

    # -- individual columns -------------------------------------------------

    def _paint_checkbox(self, painter, rect: QRect, selected: bool) -> None:
        box = QRect(0, 0, 14, 14)
        box.moveCenter(rect.center())
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(box, 2, 2)
        painter.fillPath(path, QColor(theme.CONTAINER_LOWEST))
        painter.setPen(QColor(theme.PRIMARY if selected else theme.OUTLINE))
        painter.drawPath(path)
        if selected:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.PRIMARY))
            painter.drawEllipse(box.center(), 3, 3)
        painter.restore()

    def _paint_star(self, painter, rect: QRect, favorite: bool, hovered: bool) -> None:
        painter.save()
        color = QColor(theme.AMBER if favorite
                       else (theme.ON_SURFACE if hovered else theme.OUTLINE))
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        self._draw_star(painter, QPointF(rect.center()), 7.0, filled=favorite)
        painter.restore()

    @staticmethod
    def _draw_star(painter: QPainter, center: QPointF, size: float, filled: bool) -> None:
        points: list[QPointF] = []
        for i in range(10):
            angle = -math.pi / 2 + i * math.pi / 5
            r = size if i % 2 == 0 else size * 0.45
            points.append(
                QPointF(center.x() + r * math.cos(angle),
                        center.y() + r * math.sin(angle))
            )
        path = QPainterPath()
        path.addPolygon(QPolygonF(points))
        if filled:
            painter.fillPath(path, painter.brush())
        else:
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)

    def _paint_name(self, painter, option, record) -> None:
        rect = option.rect.adjusted(8, 0, -6, 0)
        # Category glyph chip.
        glyph = QRect(rect.left(), rect.y() + (rect.height() - 16) // 2, 16, 16)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(glyph, 2, 2)
        painter.fillPath(path, QColor(theme.CONTAINER_HIGH))
        painter.setPen(QColor(theme.PRIMARY))
        f = QFont(theme.sans_family())
        f.setPointSizeF(7.0)
        f.setWeight(QFont.Bold)
        painter.setFont(f)
        painter.drawText(glyph, Qt.AlignCenter, _category_glyph(record.category))
        painter.restore()

        text_rect = rect.adjusted(glyph.width() + 6, 0, 0, 0)
        f = QFont(theme.sans_family())
        f.setPointSizeF(9.5)
        f.setWeight(QFont.Medium)
        painter.save()
        painter.setFont(f)
        fm = painter.fontMetrics()
        elided = fm.elidedText(record.name, Qt.ElideRight, text_rect.width())
        painter.setPen(QColor(theme.ON_SURFACE))
        painter.drawText(text_rect, int(Qt.AlignLeft | Qt.AlignVCenter), elided)
        painter.restore()

    def _paint_auth(self, painter, rect: QRect, auth: str) -> None:
        label, fg, border, bg = AUTH_STYLES.get(
            auth, (auth.upper() or "UNKNOWN", theme.TERTIARY, theme.TERTIARY, theme.TERTIARY)
        )
        self._paint_chip(painter, rect, label, fg, border, bg)

    def _paint_flag(self, painter, rect: QRect, value: str) -> None:
        fg, _ = _FLAG_STYLES.get(value, _FLAG_STYLES["unknown"])
        glyph = "✓" if value == "yes" else ("✕" if value == "no" else "?")
        painter.save()
        f = QFont(theme.sans_family())
        f.setPointSizeF(11.0)
        f.setWeight(QFont.Bold)
        painter.setFont(f)
        painter.setPen(QColor(fg))
        painter.drawText(rect, Qt.AlignCenter, glyph)
        painter.restore()

    def _paint_cors(self, painter, rect: QRect, value: str) -> None:
        fg, border = _FLAG_STYLES.get(value, _FLAG_STYLES["unknown"])
        label = {"yes": "YES", "no": "NO", "unknown": "N/A"}.get(value, "N/A")
        self._paint_chip(painter, rect, label, fg, border, fg)

    def _paint_category(self, painter, rect: QRect, category: str) -> None:
        painter.save()
        dot_rect = QRect(rect.left() + 8, rect.y() + (rect.height() - 6) // 2, 6, 6)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(theme.CONTAINER_HIGHEST))
        painter.drawEllipse(dot_rect)
        text_rect = rect.adjusted(dot_rect.width() + 14, 0, -6, 0)
        f = QFont(theme.sans_family())
        f.setPointSizeF(9.5)
        painter.setFont(f)
        fm = painter.fontMetrics()
        painter.setPen(QColor(theme.OUTLINE))
        painter.drawText(
            text_rect,
            int(Qt.AlignLeft | Qt.AlignVCenter),
            fm.elidedText(category, Qt.ElideRight, text_rect.width()),
        )
        painter.restore()

    def _paint_actions(self, painter, rect: QRect, hovered: bool) -> None:
        base = theme.PRIMARY if hovered else theme.OUTLINE
        painter.save()
        for i, glyph in enumerate(("⚡", "⧉", "›")):
            cell = QRect(rect.right() - 26 * (3 - i) - 4, rect.y(), 26, rect.height())
            painter.setPen(Qt.NoPen)
            painter.setBrush(Qt.NoBrush)
            f = QFont(theme.sans_family())
            f.setPointSizeF(10.0)
            painter.setFont(f)
            painter.setPen(QColor(base if i < 2 else theme.PRIMARY_CONTAINER))
            painter.drawText(cell, Qt.AlignCenter, glyph)
        painter.restore()

    def _paint_text(self, painter, option, index, color, family, size) -> None:
        rect = option.rect.adjusted(8, 0, -8, 0)
        painter.save()
        f = QFont(family)
        f.setPointSizeF(size)
        painter.setFont(f)
        fm = painter.fontMetrics()
        text = index.data(Qt.DisplayRole) or ""
        painter.setPen(QColor(color))
        painter.drawText(
            rect,
            int(Qt.AlignLeft | Qt.AlignVCenter),
            fm.elidedText(str(text), Qt.ElideRight, rect.width()),
        )
        painter.restore()

    # -- hit testing --------------------------------------------------------

    def editorEvent(self, event, model, option, index) -> bool:
        if not index.isValid():
            return False
        col = index.column()
        rect = option.rect

        if col == COL_FAVORITE:
            if event.type() == event.MouseButtonRelease:
                self.favoriteClicked.emit(index)
                return True
            return True

        if col == COL_ACTIONS:
            if event.type() == event.MouseButtonRelease:
                for code, cell in enumerate(self._action_cells(rect)):
                    if cell.contains(event.pos()):
                        self.actionClicked.emit(index, code)
                        return True
            return True

        if col == COL_CHECKBOX:
            if event.type() == event.MouseButtonRelease:
                return True
            return True

        return super().editorEvent(event, model, option, index)

    @staticmethod
    def _action_cells(rect: QRect) -> list[QRect]:
        cells = []
        for i in range(3):
            cells.append(QRect(rect.right() - 26 * (3 - i) - 4, rect.y(), 26, rect.height()))
        return cells


_GLYPHS = {
    "animals": "◕", "anime": "◠", "art": "✦", "authentication": "⚿",
    "blockchain": "⛓", "books": "▤", "business": "◫", "calendar": "▦",
    "cloud": "☁", "cryptocurrency": "◈", "development": "⌘", "education": "✎",
    "email": "✉", "finance": "◉", "food": "◔", "games": "◈", "geocoding": "⌖",
    "government": "⚑", "health": "✚", "jobs": "▣", "machine": "◰",
    "music": "♪", "news": "▤", "open data": "◱", "security": "⚿",
    "shopping": "◰", "social": "◍", "sports": "◈", "test data": "◫",
    "transportation": "⇄", "url shorteners": "⇗", "video": "▶", "weather": "☀",
}


def _category_glyph(category: str) -> str:
    return _GLYPHS.get(category.strip().lower(), "◆")