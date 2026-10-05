"""Background catalog sync.

The refresh does network I/O plus a markdown parse, which is far too slow to run
on the GUI thread. This wraps it in a QThread worker that reports back through
signals; the window never blocks and stays interactive while it runs.
"""

from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import QObject, QThread, Signal

from .catalog import Catalog
from .store import CatalogError, catalog_from_markdown, fetch_markdown, save_snapshot


class SyncWorker(QObject):
    """Fetches and parses the upstream README off the GUI thread."""

    finished = Signal(object)      # Catalog
    failed = Signal(str)           # human-readable error
    progressed = Signal(str)       # status line for the footer

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self) -> None:
        try:
            self.progressed.emit("Syncing…")
            markdown = fetch_markdown()
            self.progressed.emit("Parsing…")
            stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
            catalog = catalog_from_markdown(markdown, fetched_at=stamp)
        except CatalogError as exc:
            self.failed.emit(str(exc))
            return
        except Exception as exc:  # noqa: BLE001 - surface anything unexpected
            self.failed.emit(f"Unexpected error: {exc}")
            return

        try:
            self.progressed.emit("Saving…")
            save_snapshot(catalog)
        except OSError as exc:
            # The catalog itself is good; only persistence failed.
            self.failed.emit(f"Fetched {len(catalog.records)} APIs, "
                             f"but could not save the cache: {exc}")
            return

        self.finished.emit(catalog)


class SyncController(QObject):
    """Owns the thread lifetime so callers cannot leak a running QThread."""

    progressed = Signal(str)
    finished = Signal(object)   # Catalog
    failed = Signal(str)
    busyChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: SyncWorker | None = None

    @property
    def busy(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def start(self) -> bool:
        """Begin a refresh. Returns False if one is already running."""
        if self.busy:
            return False

        thread = QThread(self)
        worker = SyncWorker()
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progressed.connect(self.progressed)
        worker.finished.connect(self._on_finished)
        worker.failed.connect(self._on_failed)

        self._thread = thread
        self._worker = worker
        thread.start()
        self.busyChanged.emit(True)
        return True

    def _teardown(self) -> None:
        thread, worker = self._thread, self._worker
        self._thread = None
        self._worker = None
        if thread is not None:
            if worker is not None:
                # Post the worker's deletion to its OWN event loop while that
                # loop is still alive, then quit()+wait() so it is drained on
                # the way out. Destroying the worker from the GUI thread after
                # the QThread is gone leaves it with affinity to a dead thread
                # and crashes PySide.
                worker.deleteLater()
            thread.quit()
            if not thread.wait(5000):
                # Still running: leak it rather than deleting a live thread.
                return
            thread.deleteLater()
        self.busyChanged.emit(False)

    def _on_finished(self, catalog: Catalog) -> None:
        self._teardown()
        self.finished.emit(catalog)

    def _on_failed(self, message: str) -> None:
        self._teardown()
        self.failed.emit(message)

    def shutdown(self) -> None:
        """Stop cleanly on window close so Qt never reports a live thread.

        A blocking wait is acceptable here because the window is closing and
        nothing else needs the GUI thread.
        """
        thread = self._thread
        self._thread = None
        self._worker = None
        if thread is not None and thread.isRunning():
            thread.quit()
            thread.wait(3000)