"""Independent PDF preview windows with snapshots of compiled documents."""

from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow

from nd_mind_mirror.ui.preview.pdf.selectable_pdf_view import SelectablePdfView


class PinnedPdfPreviewWindow(QMainWindow):
    """Keep a rendered PDF visible independently of the active editor tab."""

    def __init__(self, source_pdf: Path, document_name: str, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self._directory = TemporaryDirectory(prefix="mind_mirror_preview_")
        self._snapshot = Path(self._directory.name) / "preview.pdf"
        shutil.copy2(source_pdf, self._snapshot)
        # Reuse the exact same selectable PDF reader as the live Preview, so
        # word double-click, drag selection and Ctrl+C work in pinned windows.
        self._viewer = SelectablePdfView(self)
        self.setCentralWidget(self._viewer)
        self.setWindowTitle(f"Pinned Preview — {document_name}")
        self.resize(780, 920)
        if not self._viewer.show_pdf(self._snapshot):
            self._directory.cleanup()
            raise OSError(f"Could not open a PDF snapshot for {document_name}.")

    def closeEvent(self, event):
        # The snapshot must survive recompiles, file switching and dismissal of
        # the main Preview, but should be deleted once this window is closed.
        self._viewer.close()
        super().closeEvent(event)
        self._directory.cleanup()
