"""Manage LaTeX documents that exist only in editor memory until Save."""

from pathlib import Path
from uuid import uuid4

from PySide6.QtWidgets import QFileDialog, QMessageBox


class TemporaryLatexDocumentController:
    def __init__(self, window):
        self._window = window
        self._pending: set[Path] = set()
        recent = window._session_settings.value("editor/last_ctrl_s_directory", "")
        self._last_directory = Path(str(recent)).expanduser() if recent and Path(str(recent)).is_dir() else None

    def contains(self, path: Path | None) -> bool:
        return path in self._pending

    def create(self) -> None:
        window = self._window
        templates = window._app_settings.new_latex_file_templates
        template = next((Path(path) for label, path in templates
                         if str(label).strip().lower() in {"default", "article (standard)"}), None)
        if template is None:
            QMessageBox.warning(window, "New LaTeX Document", "Default LaTeX template is not configured.")
            return
        try:
            content = template.read_text(encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(window, "New LaTeX Document", str(exc))
            return

        # This path is an identity only; neither the directory nor a file is created.
        path = Path.home() / ".nd_mind_mirror_unsaved" / f"Untitled-{uuid4().hex[:8]}.tex"
        self._pending.add(path)
        if not window._editor_panel.open_file(path, content):
            self._pending.discard(path)
            return
        editor = window._editor_panel.current_editor()
        if editor is not None:
            editor.document().setModified(True)
        window._save_action.setEnabled(True)

    def save(self, path: Path, content: str) -> bool:
        window = self._window
        start = self._last_directory or Path.home()
        selected, _ = QFileDialog.getSaveFileName(
            window, "Save LaTeX Document", str(start / "Untitled.tex"),
            "LaTeX files (*.tex);;All files (*)",
        )
        if not selected:
            return False
        destination = Path(selected).expanduser()
        if not destination.suffix:
            destination = destination.with_suffix(".tex")
        destination = destination.resolve()
        if destination in window._editor_panel.open_paths():
            QMessageBox.warning(
                window, "Already open",
                "This file is already open in another tab. Choose another filename.",
            )
            return False
        if destination.exists():
            decision = QMessageBox.question(
                window, "Replace existing file?",
                f"{destination} already exists. Replace it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if decision != QMessageBox.StandardButton.Yes:
                return False
        if not window._save_document(destination, content, show_error=True):
            return False
        window._editor_panel.rename_paths_under(path, destination)
        window._editor_panel.mark_saved(destination)
        self._pending.discard(path)
        self.remember_directory(destination)
        window._save_action.setEnabled(False)
        window.statusBar().showMessage(f"Saved {destination}", 3500)
        return True

    def remember_directory(self, path: Path) -> None:
        self._last_directory = path.parent
        self._window._session_settings.setValue(
            "editor/last_ctrl_s_directory", str(path.parent)
        )
        self._window._session_settings.sync()

    def forget(self, path: Path) -> None:
        self._pending.discard(path)
