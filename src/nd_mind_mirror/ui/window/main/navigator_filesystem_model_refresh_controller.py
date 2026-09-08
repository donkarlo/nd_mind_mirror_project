"""Refresh Navigator's cached filesystem model after successful external renames."""

from pathlib import Path

from PySide6.QtCore import QObject, QTimer


class NavigatorFilesystemModelRefreshController(QObject):
    """Keep QFileSystemModel synchronized after background rename/move workers finish."""

    def __init__(self, file_system_panel, parent=None) -> None:
        super().__init__(parent)
        self._panel = file_system_panel
        self._generation = 0
        self._panel.path_renamed.connect(self._on_path_renamed)

    def _on_path_renamed(self, old_path: str, new_path: str) -> None:
        """Rebuild the watched root so stale pre-rename rows cannot remain cached."""
        del old_path
        target = Path(new_path).expanduser().resolve(strict=False)
        self._generation += 1
        generation = self._generation
        expanded_paths = list(self._panel.expanded_paths())

        model = self._panel._model
        root_path = str(self._panel._root_path)

        # QFileSystemModel normally notices external changes itself, but a move
        # completed in a child process can briefly leave a cached old row. A
        # root rebind deterministically rebuilds the watcher/cache without
        # replacing the Navigator widget or its saved expansion state.
        model.setRootPath("")
        model.setRootPath(root_path)
        self._panel._proxy_model.invalidateFilter()
        self._panel._apply_root_index()
        self._panel.restore_state(expanded_paths, str(target))

        for delay_ms in (60, 220, 700):
            QTimer.singleShot(
                delay_ms,
                lambda token=generation, item=target:
                self._reveal_after_refresh(token, item),
            )

    def _reveal_after_refresh(self, generation: int, target: Path) -> None:
        """Reveal the renamed target only for the latest filesystem generation."""
        if generation != self._generation:
            return
        self._panel._proxy_model.invalidateFilter()
        self._panel._apply_root_index()
        self._panel.select_path(target, force_reveal=True)
        self._panel.state_changed.emit()
