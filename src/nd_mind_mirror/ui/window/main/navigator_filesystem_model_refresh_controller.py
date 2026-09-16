"""Refresh Navigator's filesystem cache after explicit or detected path changes."""

from pathlib import Path

from PySide6.QtCore import QObject, QTimer


class NavigatorFilesystemModelRefreshController(QObject):
    """Keep QFileSystemModel synchronized without replacing Navigator UI state."""

    def __init__(self, file_system_panel, parent=None) -> None:
        super().__init__(parent)
        self._panel = file_system_panel
        self._generation = 0
        self._panel.path_renamed.connect(self._on_path_renamed)
        self._panel.path_deleted.connect(self._on_path_deleted)
        self._panel.path_created.connect(self._on_path_created)

    def refresh(self, selected_path: str | Path | None = None) -> None:
        """Rebind the watched root and restore expansion plus a valid selection."""
        target = self._valid_target(selected_path)
        self._generation += 1
        generation = self._generation
        expanded_paths = list(self._panel.expanded_paths())

        model = self._panel._model
        root_path = str(self._panel._root_path)
        model.setRootPath("")
        model.setRootPath(root_path)
        self._panel._proxy_model.invalidateFilter()
        self._panel._apply_root_index()
        self._panel.restore_state(
            expanded_paths,
            str(target) if target is not None else "",
        )

        for delay_ms in (60, 220, 700):
            QTimer.singleShot(
                delay_ms,
                lambda token=generation, item=target:
                self._finish_refresh(token, item),
            )

    def _on_path_renamed(self, old_path: str, new_path: str) -> None:
        del old_path
        self.refresh(new_path)

    def _on_path_deleted(self, path: str) -> None:
        deleted = Path(path).expanduser().resolve(strict=False)
        self.refresh(deleted.parent)

    def _on_path_created(self, path: str) -> None:
        self.refresh(path)

    def _finish_refresh(self, generation: int, target: Path | None) -> None:
        if generation != self._generation:
            return
        self._panel._proxy_model.invalidateFilter()
        self._panel._apply_root_index()
        if target is not None and target.exists():
            self._panel.select_path(target, force_reveal=True)
        self._panel.state_changed.emit()

    def _valid_target(self, value: str | Path | None) -> Path | None:
        if value is None or str(value).strip() == "":
            selected = self._panel.selected_path()
            value = selected if selected else self._panel._root_path
        try:
            target = Path(value).expanduser().resolve(strict=False)
        except (OSError, TypeError, ValueError):
            target = self._panel._root_path

        while target != self._panel._root_path and not target.exists():
            target = target.parent
        if not target.exists():
            return None
        return target
