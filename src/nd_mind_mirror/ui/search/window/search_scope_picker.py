"""Reusable read-only folder selector for recursive search scopes."""

from pathlib import Path

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLineEdit, QPushButton, QWidget


class SearchScopePicker(QWidget):
    """Display a search root and select it through the native folder dialog."""

    path_changed = Signal(str)

    def __init__(self, initial_path: str | Path, parent=None) -> None:
        """Initialize the read-only search-scope selector."""
        super().__init__(parent)
        self._path = self._validated_path(initial_path)

        self._path_edit = QLineEdit(self)
        self._path_edit.setReadOnly(True)
        self._path_edit.setPlaceholderText("Select the folder to search below…")
        self._path_edit.installEventFilter(self)

        self._browse_button = QPushButton("Browse…", self)
        self._browse_button.clicked.connect(self.choose_folder)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._path_edit, 1)
        layout.addWidget(self._browse_button)

        self._refresh_text()

    @property
    def path(self) -> Path:
        """Return the current recursive search root."""
        return self._path

    def set_path(self, path: str | Path, emit: bool = True) -> None:
        """Use an existing directory as the search root."""
        candidate = self._validated_path(path)
        if candidate == self._path:
            self._refresh_text()
            return

        self._path = candidate
        self._refresh_text()
        if emit:
            self.path_changed.emit(str(candidate))

    def choose_folder(self) -> None:
        """Open the native filesystem chooser instead of allowing typed paths."""
        selected = QFileDialog.getExistingDirectory(
            self,
            "Select Search Folder",
            str(self._path),
            QFileDialog.Option.ShowDirsOnly,
        )
        if not selected:
            return
        self.set_path(selected, emit=True)

    def eventFilter(self, watched, event) -> bool:
        """Open the folder chooser from mouse or keyboard activation."""
        if watched is self._path_edit:
            if event.type() == QEvent.Type.MouseButtonPress:
                self.choose_folder()
                return True
            if event.type() == QEvent.Type.KeyPress and event.key() in {
                Qt.Key.Key_Return,
                Qt.Key.Key_Enter,
                Qt.Key.Key_Space,
            }:
                self.choose_folder()
                return True
        return super().eventFilter(watched, event)

    def _refresh_text(self) -> None:
        """Mirror the selected path into the read-only display field."""
        self._path_edit.setText(str(self._path))
        self._path_edit.setToolTip(str(self._path))

    @staticmethod
    def _validated_path(path: str | Path) -> Path:
        """Return an existing resolved directory or the user home directory."""
        candidate = Path(path).expanduser()
        try:
            if candidate.is_dir():
                return candidate.resolve()
        except OSError:
            pass
        return Path.home().resolve()
