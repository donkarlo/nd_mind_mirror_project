"""Independent, searchable PDF snapshots that retain their own selection state."""

from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from nd_mind_mirror.ui.preview.pdf.selectable_pdf_view import SelectablePdfView
from nd_mind_mirror.ui.window.main.preview.preview_find_controller import (
    PreviewFindController,
)


class PinnedPdfPreviewWindow(QMainWindow):
    """Keep an independently searchable, copyable PDF snapshot open."""

    def __init__(self, source_pdf: Path, document_name: str, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self._directory = TemporaryDirectory(prefix="mind_mirror_preview_")
        self._snapshot = Path(self._directory.name) / "preview.pdf"
        shutil.copy2(source_pdf, self._snapshot)

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._viewer = SelectablePdfView(container)
        self._viewer.enable_copy_context_menu()
        layout.addWidget(self._viewer, 1)
        self._find_controller = PreviewFindController(
            container,
            viewer=self._viewer,
            pdf_path_provider=lambda: self._snapshot,
            insert_layout=layout,
            insert_index=0,
        )
        self.setCentralWidget(container)
        self._find_shortcut = QShortcut(QKeySequence.StandardKey.Find, container)
        self._find_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._find_shortcut.activated.connect(self._find_controller.show)

        self.setWindowTitle(f"Pinned Preview — {document_name}")
        self.resize(780, 920)
        if not self._viewer.show_pdf(self._snapshot):
            self._directory.cleanup()
            raise OSError(f"Could not open a PDF snapshot for {document_name}.")

    def closeEvent(self, event):
        # The snapshot remains available until this particular window closes.
        self._find_controller.close_document()
        self._viewer.close()
        super().closeEvent(event)
        self._directory.cleanup()
