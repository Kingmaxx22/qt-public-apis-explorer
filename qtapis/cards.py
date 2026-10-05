"""Card / grid view of the API catalog.

The Stitch mock shows a card toggle but ships no card artwork, so this layout is
derived from the design tokens themselves:
  surface-container-low   card background
  surface-container-high  category glyph chip
  outline-variant         hairline card border
  space-xl (16px)         card padding, per DESIGN.md spacing rhythm
  rounded (4px)           card radius, per DESIGN.md "Shapes"
  label-badge (10px mono) the NO AUTH / API KEY / OAUTH chips
"""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QGridLayout,
    QScrollArea,
    QSizePolicy,
    QWidget,
)

from . import theme
from .catalog import ApiRecord
from .delegates import AUTH_STYLES, _FLAG_STYLES, _category_glyph

alpha = theme.alpha

CARD_PAD = theme.space_px("space-xl")      # 16px
CARD_GAP = theme.space_px("space-lg")       # 12px
CARD_RADIUS = theme.RAD_INPUT              # 4px
MIN_CARD_W = 300
CARD_H = 126


class ApiCard(QWidget):
    """One API rendered as a dense, hairline-bordered card."""

    activated = Signal(object)  # ApiRecord
    favoriteToggled = Signal(object)

    def __init__(self, record: ApiRecord, parent=None):
        super().__init__(parent)
        self.record = record
        self._hover = False
        self.setFixedHeight(CARD_H)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

    # -- painting ----------------------------------------------------------

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = QRect(0, 0, self.width(), self.height())

        path = QPainterPath()
        path.addRoundedRect(rect, CARD_RADIUS, CARD_RADIUS)
        p.fillPath(path, QColor(theme.CONTAINER_LOW))
        p.setPen(QColor(theme.PRIMARY_CONTAINER if self._hover
                        else theme.OUTLINE_VARIANT))
        p.drawPath(path)
        if self.record.favorite:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(theme.AMBER))
            p.drawRoundedRect(QRect(0, 0, 3, self.height()), 1.5, 1.5)

        x = CARD_PAD
        y = CARD_PAD
        right = self.width() - CARD_PAD

        # Category glyph ----------------------------------------------------
        glyph = QRect(x, y, 18, 18)
        gp = QPainterPath()
        gp.addRoundedRect(glyph, 2, 2)
        p.fillPath(gp, QColor(theme.CONTAINER_HIGH))
        p.setPen(QColor(theme.PRIMARY))
        gf = QFont(theme.sans_family())
        gf.setPointSizeF(8.0)
        gf.setWeight(QFont.Bold)
        p.setFont(gf)
        p.drawText(glyph, Qt.AlignCenter, _category_glyph(self.record.category))

        # Auth chip (right-aligned on the title row) ------------------------
        label, fg, border, bg = AUTH_STYLES.get(
            self.record.auth,
            (self.record.auth.upper() or "?",
             theme.TERTIARY, theme.TERTIARY, theme.TERTIARY),
        )
        cf = QFont(theme.mono_family())
        cf.setPointSizeF(8.0)
        cf.setWeight(QFont.DemiBold)
        p.setFont(cf)
        chip_w = p.fontMetrics().horizontalAdvance(label) + 12
        chip = QRect(right - chip_w, y, chip_w, 18)
        cp = QPainterPath()
        cp.addRoundedRect(chip, 2, 2)
        p.fillPath(cp, alpha(bg, 0.14))
        p.setPen(QColor(border))
        p.drawPath(cp)
        p.setPen(QColor(fg))
        p.drawText(chip, Qt.AlignCenter, label)

        # Title --------------------------------------------------------------
        tf = QFont(theme.sans_family())
        tf.setPointSizeF(10.5)
        tf.setWeight(QFont.DemiBold)
        p.setFont(tf)
        fm = p.fontMetrics()
        title_rect = QRect(glyph.right() + 8, y, chip.left() - glyph.right() - 16,
                           18)
        p.setPen(QColor(theme.ON_SURFACE))
        p.drawText(title_rect, int(Qt.AlignLeft | Qt.AlignVCenter),
                   fm.elidedText(self.record.name, Qt.ElideRight,
                                 title_rect.width()))

        # Category -----------------------------------------------------------
        y += 24
        cat_f = QFont(theme.sans_family())
        cat_f.setPointSizeF(8.5)
        p.setFont(cat_f)
        p.setPen(QColor(theme.OUTLINE))
        p.drawText(QRect(x, y, self.width() - 2 * CARD_PAD, 14),
                   int(Qt.AlignLeft | Qt.AlignVCenter),
                   fm.elidedText(self.record.category, Qt.ElideRight,
                                 self.width() - 2 * CARD_PAD))

        # Description ---------------------------------------------------------
        y += 18
        df = QFont(theme.sans_family())
        df.setPointSizeF(9.0)
        p.setFont(df)
        dfm = p.fontMetrics()
        desc_rect = QRect(x, y, self.width() - 2 * CARD_PAD, 32)
        p.setPen(QColor(theme.ON_SURFACE_VARIANT))
        text = self.record.description or "No description provided."
        p.drawText(
            desc_rect,
            int(Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap),
            dfm.elidedText(text, Qt.ElideRight, desc_rect.width(), 2),
        )

        # Footer chips ---------------------------------------------------------
        fy = self.height() - CARD_PAD - 16
        fx = x
        chip_specs = (
            ("HTTPS", self.record.https),
            ("CORS", self.record.cors),
        )
        for label, value in chip_specs:
            fg, _ = _FLAG_STYLES.get(value, _FLAG_STYLES["unknown"])
            if label == "HTTPS" and value == "yes":
                fg = theme.SECONDARY
            elif label == "HTTPS":
                fg = theme.ERROR
            text_label = label if value != "unknown" else f"{label} ?"
            f2 = QFont(theme.mono_family())
            f2.setPointSizeF(8.0)
            f2.setWeight(QFont.DemiBold)
            p.setFont(f2)
            w = p.fontMetrics().horizontalAdvance(text_label) + 12
            cbox = QRect(fx, fy, w, 16)
            cpath = QPainterPath()
            cpath.addRoundedRect(cbox, 2, 2)
            p.fillPath(cpath, alpha(fg, 0.14))
            p.setPen(QColor(fg))
            p.drawPath(cpath)
            p.drawText(cbox, Qt.AlignCenter, text_label)
            fx += w + 6

        # URL -----------------------------------------------------------------
        p.setFont(cf)
        url_rect = QRect(fx, fy, right - fx, 16)
        p.setPen(QColor(theme.OUTLINE))
        p.drawText(url_rect, int(Qt.AlignRight | Qt.AlignVCenter),
                   p.fontMetrics().elidedText(
                       self.record.url, Qt.ElideLeft, url_rect.width()))
        p.end()

    # -- interaction ---------------------------------------------------------

    def enterEvent(self, event):
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.activated.emit(self.record)


class CardView(QScrollArea):
    """Flowing grid of ApiCards, sized to the viewport width."""

    cardActivated = Signal(object)
    favoriteToggled = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._records: list[ApiRecord] = []
        self._cards: list[ApiCard] = []
        self._rebuild_queued = False

        self._host = QWidget()
        self._grid = QGridLayout(self._host)
        self._grid.setContentsMargins(CARD_GAP, CARD_GAP, CARD_GAP, CARD_GAP)
        self._grid.setSpacing(CARD_GAP)
        self.setWidget(self._host)

    def set_records(self, records: list[ApiRecord]) -> None:
        self._records = list(records)
        self._rebuild()

    def _clear(self) -> None:
        # Remove through the layout only. Unparenting a widget that is still
        # referenced by a layout item leaves a dangling entry and the grid
        # stops painting.
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._cards.clear()

    def _rebuild(self) -> None:
        self._clear()
        if not self._records:
            return
        per_row = max(1, (self.viewport().width() - CARD_GAP) //
                      (MIN_CARD_W + CARD_GAP))
        card_w = max(MIN_CARD_W, (self.viewport().width()
                                  - CARD_GAP * (per_row + 1)) // per_row)
        for i, record in enumerate(self._records):
            card = ApiCard(record)
            card.setFixedWidth(card_w)
            card.activated.connect(self.cardActivated)
            self._grid.addWidget(card, i // per_row, i % per_row)
            self._cards.append(card)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Rebuilding children from inside resizeEvent re-enters layout code;
        # defer it to the next event-loop turn instead.
        if self._rebuild_queued:
            return
        self._rebuild_queued = True
        QTimer.singleShot(0, self._deferred_rebuild)

    def _deferred_rebuild(self) -> None:
        self._rebuild_queued = False
        if self.isVisible():
            self._rebuild()

    def card_count(self) -> int:
        return len(self._cards)

    def card_at(self, i: int) -> ApiCard | None:
        if 0 <= i < len(self._cards):
            return self._cards[i]
        return None