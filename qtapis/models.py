"""Qt item models for the API grid."""

from __future__ import annotations

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QSortFilterProxyModel,
    Qt,
    Signal,
)

from .catalog import ApiRecord

# Column order mirrors the mock's <thead>.
COL_CHECKBOX = 0
COL_FAVORITE = 1
COL_NAME = 2
COL_DESCRIPTION = 3
COL_AUTH = 4
COL_HTTPS = 5
COL_CORS = 6
COL_CATEGORY = 7
COL_ACTIONS = 8
COLUMN_COUNT = 9

COLUMN_LABELS = [
    "",
    "",
    "API Identifier",
    "Description",
    "Auth Type",
    "HTTPS",
    "CORS",
    "Category",
    "Actions",
]

# Which column drives which filter (used by the proxy).
AUTH_ANY = "all"


class RecordStore(QObject):
    """Holds the catalog and notifies views when favorites or the data change."""

    favoritesChanged = Signal()
    catalogReplaced = Signal()

    def __init__(self, records: list[ApiRecord], fetched_at: str = "", parent=None):
        super().__init__(parent)
        self.records = list(records)
        self.fetched_at = fetched_at

    def replace(self, records: list[ApiRecord], fetched_at: str = "") -> None:
        self.records = list(records)
        self.fetched_at = fetched_at
        self.catalogReplaced.emit()

    def toggle_favorite(self, record: ApiRecord) -> None:
        record.favorite = not record.favorite
        self.favoritesChanged.emit()

    def category_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self.records:
            counts[r.category] = counts.get(r.category, 0) + 1
        return counts

    def favorite_count(self) -> int:
        return sum(1 for r in self.records if r.favorite)


class ApiTableModel(QAbstractTableModel):
    """Exposes a list of ApiRecord as the 9-column high-density grid."""

    favoriteToggled = Signal(object)  # ApiRecord

    def __init__(self, store: RecordStore, parent=None):
        super().__init__(parent)
        self.store = store
        store.favoritesChanged.connect(self._on_favorites_changed)
        store.catalogReplaced.connect(self._on_catalog_replaced)

    # -- Qt plumbing --------------------------------------------------------

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.store.records)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else COLUMN_COUNT

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return COLUMN_LABELS[section]
        if role == Qt.TextAlignmentRole and orientation == Qt.Horizontal:
            if section in (COL_CHECKBOX, COL_FAVORITE, COL_HTTPS, COL_CORS):
                return int(Qt.AlignCenter)
            if section == COL_ACTIONS:
                return int(Qt.AlignRight | Qt.AlignVCenter)
            return int(Qt.AlignLeft | Qt.AlignVCenter)
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        base = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if index.column() in (COL_CHECKBOX, COL_FAVORITE):
            return base | Qt.ItemIsUserCheckable
        return base

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        record = self.store.records[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            return {
                COL_NAME: record.name,
                COL_DESCRIPTION: record.description,
                COL_AUTH: record.auth,
                COL_HTTPS: record.https,
                COL_CORS: record.cors,
                COL_CATEGORY: record.category,
            }.get(col)

        if role == Qt.CheckStateRole and col == COL_CHECKBOX:
            return Qt.Unchecked

        if role == Qt.UserRole:
            # Payload channel used by delegates and click handlers.
            return record

        if role == Qt.TextAlignmentRole:
            if col in (COL_CHECKBOX, COL_FAVORITE, COL_HTTPS, COL_CORS, COL_ACTIONS):
                return int(Qt.AlignCenter)
            return int(Qt.AlignLeft | Qt.AlignVCenter)

        if role == Qt.ToolTipRole:
            return f"{record.name}\n{record.url}"

        return None

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid():
            return False
        record = self.store.records[index.row()]
        if index.column() == COL_FAVORITE and role in (
            Qt.EditRole,
            Qt.CheckStateRole,
        ):
            want = (
                bool(value)
                if role == Qt.CheckStateRole
                else value == Qt.Checked
            )
            if record.favorite != want:
                self.store.toggle_favorite(record)
                self.favoriteToggled.emit(record)
            return True
        if index.column() == COL_CHECKBOX and role == Qt.CheckStateRole:
            return True
        return False

    # -- helpers ------------------------------------------------------------

    def record_at(self, row: int) -> ApiRecord | None:
        if 0 <= row < len(self.store.records):
            return self.store.records[row]
        return None

    def _on_favorites_changed(self) -> None:
        if not self.store.records:
            return
        top = self.index(0, 0)
        bottom = self.index(len(self.store.records) - 1, COLUMN_COUNT - 1)
        self.dataChanged.emit(top, bottom, [Qt.UserRole])

    def _on_catalog_replaced(self) -> None:
        self.beginResetModel()
        self.endResetModel()


class ApiFilterProxy(QSortFilterProxyModel):
    """Applies free-text search plus the toolbar's auth/HTTPS/CORS filters."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.query = ""
        self.auth = AUTH_ANY
        self.https = "any"
        self.cors = "any"
        self.category: str | None = None
        self.favorites_only = False
        self.setSortRole(Qt.UserRole)

    def set_query(self, text: str) -> None:
        text = text.strip().lower()
        if text != self.query:
            self.query = text
            self.invalidateFilter()

    def _matches(self, record: ApiRecord) -> bool:
        if self.favorites_only and not record.favorite:
            return False
        if self.category is not None and record.category != self.category:
            return False
        if self.auth != AUTH_ANY and record.auth != self.auth:
            return False
        if self.https != "any" and record.https != self.https:
            return False
        if self.cors != "any" and record.cors != self.cors:
            return False
        if self.query:
            haystack = " ".join(
                (record.name, record.description, record.category, record.url)
            ).lower()
            # Every whitespace-separated term must appear somewhere.
            if not all(term in haystack for term in self.query.split()):
                return False
        return True

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        model = self.sourceModel()
        index = model.index(source_row, 0, source_parent)
        record = index.data(Qt.UserRole)
        return self._matches(record) if record is not None else False

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        a: ApiRecord = left.data(Qt.UserRole)
        b: ApiRecord = right.data(Qt.UserRole)
        if a is None or b is None:
            return False
        col = left.column()
        if col == COL_NAME:
            return a.name.lower() < b.name.lower()
        if col == COL_AUTH:
            return (a.auth, a.name.lower()) < (b.auth, b.name.lower())
        if col == COL_HTTPS:
            return (_flag_rank(a.https), a.name.lower()) < (
                _flag_rank(b.https), b.name.lower()
            )
        if col == COL_CORS:
            return (_flag_rank(a.cors), a.name.lower()) < (
                _flag_rank(b.cors), b.name.lower()
            )
        if col == COL_CATEGORY:
            return (a.category.lower(), a.name.lower()) < (
                b.category.lower(), b.name.lower()
            )
        if col == COL_DESCRIPTION:
            return (a.description.lower(), a.name.lower()) < (
                b.description.lower(), b.name.lower()
            )
        # Icon-only columns carry no comparable payload; keep a stable order.
        return a.name.lower() < b.name.lower()


_FLAG_ORDER = {"yes": 0, "no": 1, "unknown": 2}


def _flag_rank(value: str) -> int:
    return _FLAG_ORDER.get(value, 3)