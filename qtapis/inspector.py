"""Right-docked detail inspector with a live cURL generator."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .catalog import ApiRecord
from .curlgen import auth_hint, build_curl


class Inspector(QWidget):
    """Shows the selected API plus its generated cURL command."""

    statusMessage = Signal(str)
    favoriteRequested = Signal(object)  # ApiRecord

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("inspector")
        self.setMinimumWidth(300)
        self.setMaximumWidth(720)
        self._record: ApiRecord | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        self._body = QVBoxLayout(body)
        self._body.setContentsMargins(12, 12, 12, 12)
        self._body.setSpacing(14)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        self._placeholder = QLabel("Select an API to inspect its details")
        self._placeholder.setObjectName("emptyState")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._body.addWidget(self._placeholder)
        self._body.addStretch(1)

    # -- construction -------------------------------------------------------

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("inspectorHeader")
        header.setFixedHeight(56)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(8)

        col = QVBoxLayout()
        col.setSpacing(2)
        self.header_title = QLabel("Inspector")
        self.header_title.setObjectName("inspectorTitle")
        col.addWidget(self.header_title)
        self.header_sub = QLabel("No selection")
        self.header_sub.setObjectName("fieldKey")
        col.addWidget(self.header_sub)
        layout.addLayout(col, 1)

        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("inspectorClose")
        self.close_btn.setFixedSize(26, 26)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.close_btn, 0, Qt.AlignTop)
        return header

    def _clear_body(self) -> None:
        while self._body.count():
            item = self._body.takeAt(0)
            w = item.widget()
            if w is not None:
                # Reparent immediately: deleteLater() alone leaves the widget
                # parented and painting at its last position until the event
                # loop spins, which visually overlaps the new content.
                w.setParent(None)
                w.deleteLater()

    # -- public API ---------------------------------------------------------

    def set_record(self, record: ApiRecord | None) -> None:
        self._record = record
        self._clear_body()
        if record is None:
            self.header_title.setText("Inspector")
            self.header_sub.setText("No selection")
            self._placeholder = QLabel("Select an API to inspect its details")
            self._placeholder.setObjectName("emptyState")
            self._placeholder.setAlignment(Qt.AlignCenter)
            self._body.addWidget(self._placeholder)
            self._body.addStretch(1)
            return

        self.header_title.setText(record.name)
        self.header_sub.setText(record.category)

        # Description -------------------------------------------------------
        self._body.addWidget(self._section_label("DESCRIPTION"))
        desc = QLabel(record.description or "No description provided.")
        desc.setObjectName("descText")
        desc.setWordWrap(True)
        desc.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self._body.addWidget(desc)

        # cURL well --------------------------------------------------------
        self._body.addWidget(self._section_label("CURL COMMAND"))
        self._body.addWidget(self._build_curl_well(record))

        # Protocol fields ---------------------------------------------------
        self._body.addWidget(self._section_label("PROTOCOL"))
        self._body.addWidget(self._field("ENDPOINT", record.url or "—", mono=True))
        self._body.addWidget(self._field("AUTH", _auth_label(record.auth)))
        self._body.addWidget(self._field("HTTPS", record.https.upper()))
        self._body.addWidget(self._field("CORS", record.cors.upper()))
        self._body.addWidget(self._field("CATEGORY", record.category))

        # Buttons -----------------------------------------------------------
        self._body.addWidget(self._section_label("ACTIONS"))
        open_btn = QPushButton("Open Documentation")
        open_btn.setObjectName("primaryCta")
        open_btn.setCursor(Qt.PointingHandCursor)
        open_btn.clicked.connect(self._open_url)
        self._body.addWidget(open_btn)

        row = QHBoxLayout()
        row.setSpacing(8)
        copy_btn = QPushButton("Copy cURL")
        copy_btn.setObjectName("secondaryCta")
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.clicked.connect(self.copy_curl)
        row.addWidget(copy_btn)

        fav_btn = QPushButton(
            "Unfavorite" if record.favorite else "Add to Favorites"
        )
        fav_btn.setObjectName("secondaryCta")
        fav_btn.setCursor(Qt.PointingHandCursor)
        fav_btn.clicked.connect(self._toggle_favorite)
        row.addWidget(fav_btn)
        self._body.addLayout(row)

        self._body.addStretch(1)

    # -- builders -----------------------------------------------------------

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sectionLabel")
        return label

    def _field(self, key: str, value: str, mono: bool = True) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        k = QLabel(key)
        k.setObjectName("fieldKey")
        layout.addWidget(k)

        v = QLabel(value)
        v.setObjectName("fieldValue" if mono else "descText")
        v.setWordWrap(True)
        v.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(v)
        return box

    def _build_curl_well(self, record: ApiRecord) -> QWidget:
        well = QWidget()
        well.setObjectName("curlWell")
        well.setMinimumWidth(0)
        well.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Minimum)

        outer = QVBoxLayout(well)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Editable endpoint ------------------------------------------------
        ep_bar = QHBoxLayout()
        ep_bar.setContentsMargins(8, 4, 8, 0)
        ep_bar.setSpacing(6)
        ep_tag = QLabel("ENDPOINT")
        ep_tag.setObjectName("fieldKey")
        ep_bar.addWidget(ep_tag)
        ep_tag.setMaximumWidth(56)

        self.endpoint_edit = QLineEdit(record.url or "")
        self.endpoint_edit.setObjectName("endpointInput")
        self.endpoint_edit.setPlaceholderText(
            "Paste the live endpoint path…"
        )
        self.endpoint_edit.setClearButtonEnabled(True)
        self.endpoint_edit.setFont(QFont(theme.mono_family(), 8))
        self.endpoint_edit.setMinimumWidth(60)
        self.endpoint_edit.setSizePolicy(QSizePolicy.Ignored,
                                        QSizePolicy.Fixed)
        self.endpoint_edit.textChanged.connect(self._regenerate_curl)
        ep_bar.addWidget(self.endpoint_edit, 1)

        reset_btn = QPushButton("↺")
        reset_btn.setObjectName("miniButton")
        reset_btn.setToolTip("Reset to the registry link")
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.clicked.connect(self._reset_endpoint)
        ep_bar.addWidget(reset_btn)
        outer.addLayout(ep_bar)

        self.endpoint_note = QLabel(
            "The registry links to documentation, not a live resource."
        )
        self.endpoint_note.setObjectName("fieldKey")
        self.endpoint_note.setWordWrap(True)
        self.endpoint_note.setMinimumWidth(0)
        self.endpoint_note.setSizePolicy(QSizePolicy.Ignored,
                                         QSizePolicy.Minimum)
        self.endpoint_note.setContentsMargins(8, 2, 8, 0)
        outer.addWidget(self.endpoint_note)

        # Command ----------------------------------------------------------
        bar = QHBoxLayout()
        bar.setContentsMargins(8, 4, 8, 4)
        bar.setSpacing(6)
        tag = QLabel("sh")
        tag.setObjectName("fieldKey")
        bar.addWidget(tag)
        self.auth_hint = QLabel(auth_hint(record))
        self.auth_hint.setObjectName("fieldKey")
        self.auth_hint.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.auth_hint.setMinimumWidth(0)
        bar.addWidget(self.auth_hint, 1)
        copy_btn = QPushButton("Copy cURL")
        copy_btn.setObjectName("miniButton")
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.clicked.connect(self.copy_curl)
        bar.addWidget(copy_btn)
        outer.addLayout(bar)

        self.curl_edit = QPlainTextEdit(self._curl_text())
        self.curl_edit.setObjectName("curlText")
        self.curl_edit.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.curl_edit.setMinimumWidth(0)
        self.curl_edit.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.curl_edit.setReadOnly(True)
        self.curl_edit.setFrameShape(QPlainTextEdit.NoFrame)
        self.curl_edit.setFixedHeight(76)
        f = QFont(theme.mono_family())
        f.setPointSizeF(8.5)
        self.curl_edit.setFont(f)
        outer.addWidget(self.curl_edit)
        return well

    def _endpoint(self) -> str:
        edit = getattr(self, "endpoint_edit", None)
        if edit is None:
            return ""
        return edit.text().strip()

    def _curl_text(self) -> str:
        if self._record is None:
            return ""
        return build_curl(self._record, self._endpoint() or None)

    def _regenerate_curl(self, text: str) -> None:
        """Re-render the command whenever the endpoint field changes."""
        if self._record is None or getattr(self, "curl_edit", None) is None:
            return
        overridden = bool(text.strip()) and text.strip() != self._record.url
        self.endpoint_note.setText(
            "Custom endpoint active." if overridden
            else "The registry links to documentation, not a live resource."
        )
        cursor = self.curl_edit.textCursor()
        pos = cursor.position()
        self.curl_edit.setPlainText(self._curl_text())
        cursor.setPosition(min(pos, len(self._curl_text())))
        self.curl_edit.setTextCursor(cursor)

    def _reset_endpoint(self) -> None:
        if self._record is None:
            return
        self.endpoint_edit.setText(self._record.url or "")

    # -- actions ------------------------------------------------------------

    def copy_curl(self) -> None:
        from PySide6.QtWidgets import QApplication

        if self._record is None:
            return
        QApplication.clipboard().setText(self._curl_text())
        self.statusMessage.emit(f"Copied cURL for {self._record.name}")

    def _open_url(self) -> None:
        if self._record is None or not self._record.url:
            return
        QDesktopServices.openUrl(QUrl(self._record.url))

    def _toggle_favorite(self) -> None:
        if self._record is not None:
            self.favoriteRequested.emit(self._record)


def _auth_label(auth: str) -> str:
    return {
        "none": "None required",
        "apikey": "API key",
        "oauth": "OAuth 2.0",
    }.get(auth, auth)