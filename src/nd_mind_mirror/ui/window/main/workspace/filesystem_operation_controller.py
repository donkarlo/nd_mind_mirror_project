"""Run Navigator filesystem mutations in a child process while the editor stays responsive."""

from __future__ import annotations

import json
import os
import sys
from collections import deque
from pathlib import Path
from types import MethodType

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer
from PySide6.QtWidgets import QApplication, QDialog, QInputDialog, QLineEdit, QMessageBox

from nd_mind_mirror.core.workspace.path.workspace_reference_resolver import (
    WorkspaceReferenceResolver,
)
from nd_mind_mirror.ui.window.main.workspace.reference_delete_dialog import (
    ReferenceDeleteDialog,
)


class WorkspaceFilesystemOperationController(QObject):
    """Own asynchronous rename/move/delete execution after synchronous UI preflight."""

    _WORKER_MODULE = (
        "nd_mind_mirror.core.workspace.operation.filesystem_operation_worker"
    )
    _AUTOSAVE_DRAIN_POLL_MS = 20

    def __init__(self, window, parent=None) -> None:
        """Create the serialized filesystem worker and install Navigator delegates."""
        super().__init__(parent)
        self._window = window
        self._panel = window._file_system_panel
        self._editor_panel = window._editor_panel
        self._queue: deque[dict[str, object]] = deque()
        self._active_request: dict[str, object] | None = None
        self._active_payload = b""

        self._start_timer = QTimer(self)
        self._start_timer.setSingleShot(True)
        self._start_timer.setInterval(self._AUTOSAVE_DRAIN_POLL_MS)
        self._start_timer.timeout.connect(self._try_start_next)

        self._process = QProcess(self)
        self._process.started.connect(self._send_active_request)
        self._process.finished.connect(self._on_process_finished)
        self._process.errorOccurred.connect(self._on_process_error)
        self._configure_process_environment()

        application = QApplication.instance()
        if application is not None:
            application.aboutToQuit.connect(self.shutdown)

        QTimer.singleShot(0, self._install_panel_delegates)

    @property
    def has_pending_work(self) -> bool:
        """Return whether filesystem work is queued, draining autosave, or executing."""
        return bool(
            self._queue
            or self._active_request is not None
            or self._start_timer.isActive()
            or self._process.state() != QProcess.ProcessState.NotRunning
        )

    def rename_path(self, path: Path) -> None:
        """Collect a new name synchronously, then queue the filesystem rename."""
        path = Path(path).expanduser().resolve(strict=False)
        name, accepted = QInputDialog.getText(
            self._panel,
            "Rename",
            "New name:",
            QLineEdit.EchoMode.Normal,
            path.name,
        )
        if not accepted:
            return
        normalized = name.strip()
        if not normalized or normalized == path.name:
            return
        target = path.with_name(normalized).resolve(strict=False)
        if target.exists() or target.is_symlink():
            QMessageBox.warning(
                self._panel,
                "Rename",
                f"{target.name} already exists.",
            )
            return

        self._panel.path_about_to_move.emit(str(path))
        self.request_moves([(path, target)])

    def move_path_by_drop(self, source: Path, destination: Path) -> bool:
        """Queue all selected top-level Navigator paths into one destination batch."""
        try:
            destination = Path(destination).expanduser().resolve(strict=False)
        except (OSError, TypeError, ValueError):
            return False
        if not destination.is_dir():
            return False

        sources = self._selected_paths(fallback=source)
        sources = [item for item in sources if item.parent != destination]
        if not sources:
            return False

        moves: list[tuple[Path, Path]] = []
        destinations: set[Path] = set()
        for item in sources:
            if item.is_dir() and self._same_or_child(destination, item):
                QMessageBox.warning(
                    self._panel,
                    "Move",
                    f"Cannot move {item.name} into itself.",
                )
                return False
            target = (destination / item.name).resolve(strict=False)
            if target in destinations:
                QMessageBox.warning(
                    self._panel,
                    "Move",
                    f"More than one selected path would become {target.name}.",
                )
                return False
            if target.exists() or target.is_symlink():
                QMessageBox.warning(
                    self._panel,
                    "Move",
                    f"{target.name} already exists in {destination}.",
                )
                return False
            destinations.add(target)
            moves.append((item, target))

        for item, _target in moves:
            self._panel.path_about_to_move.emit(str(item))
        return self.request_moves(moves)

    def delete_path(self, path: Path) -> bool:
        """Preserve single-delete occurrence and confirmation dialogs before queueing."""
        target = Path(path).expanduser().resolve(strict=False)
        if target == self._panel._root_path or not target.exists():
            return False

        resolver = self._workspace_resolver()
        usages = resolver.find_usages(
            resolver.default_path or self._panel._root_path,
            target,
            ignore_file_path=self._window._app_settings.search_ignore_file_path,
        )
        if usages:
            from nd_mind_mirror.ui.window.main.workspace_reference_controller import (
                WorkspaceReferenceController,
            )

            dialog = ReferenceDeleteDialog(
                self._window,
                target,
                usages,
                WorkspaceReferenceController.jump_to_usage,
                parent=self._panel,
            )
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return True

        kind = "folder" if target.is_dir() else "file"
        decision = QMessageBox.warning(
            self._panel,
            "Delete",
            f"Delete this {kind} permanently?\n\n{target}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if decision != QMessageBox.StandardButton.Yes:
            return True

        maintenance = self._reference_maintenance_controller()
        if maintenance is not None:
            maintenance.register_delete_reference_cleanup(
                {target: usages},
                resolver,
            )
        accepted = self.request_deletions([target])
        if not accepted and maintenance is not None:
            maintenance.cancel_delete_reference_cleanup([target])
        return True

    def delete_selected_paths(self) -> bool:
        """Preserve the existing Yes/No/Cancel multi-delete preflight before queueing."""
        paths = self._selected_paths()
        if not paths:
            return False

        decision = QMessageBox.question(
            self._panel,
            "Delete selected paths",
            "Delete the selected file(s)/folder(s)?\n\n"
            "Yes: search the source root and remove LaTeX commands that reference them.\n"
            "No: delete the paths only.\n"
            "Cancel: do nothing.",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if decision == QMessageBox.StandardButton.Cancel:
            return True

        remove_references = decision == QMessageBox.StandardButton.Yes
        resolver: WorkspaceReferenceResolver | None = None
        usages_by_target = {}
        if remove_references:
            resolver = self._workspace_resolver()
            root = resolver.default_path or self._panel._root_path
            ignore_path = self._window._app_settings.search_ignore_file_path
            for target in paths:
                usages_by_target[target] = resolver.find_usages(
                    root,
                    target,
                    ignore_file_path=ignore_path,
                )

        maintenance = self._reference_maintenance_controller()
        if remove_references and resolver is not None and maintenance is not None:
            maintenance.register_delete_reference_cleanup(
                usages_by_target,
                resolver,
            )

        accepted = self.request_deletions(paths)
        if not accepted and maintenance is not None:
            maintenance.cancel_delete_reference_cleanup(paths)
        return True

    def request_moves(self, mappings: list[tuple[Path, Path]]) -> bool:
        """Queue a validated move batch and guard its source paths from autosave."""
        normalized: list[tuple[Path, Path]] = []
        for source, destination in mappings:
            source_path = Path(source).expanduser().resolve(strict=False)
            destination_path = Path(destination).expanduser().resolve(strict=False)
            if source_path == destination_path:
                continue
            normalized.append((source_path, destination_path))
        if not normalized:
            return False

        roots = [source for source, _destination in normalized]
        self._block_autosave(roots)
        self._queue.append(
            {
                "moves": [
                    {"source": str(source), "destination": str(destination)}
                    for source, destination in normalized
                ],
                "deletes": [],
                "guard_roots": roots,
            }
        )
        self._operation_state_changed()
        self._start_timer.start(0)
        self._window.statusBar().showMessage(
            "Moving path(s) in the background…",
            3000,
        )
        return True

    def request_deletions(self, paths: list[Path]) -> bool:
        """Queue one top-level delete batch and guard its paths from autosave."""
        normalized = self._top_level_paths(paths)
        if not normalized:
            return False
        self._block_autosave(normalized)
        self._queue.append(
            {
                "moves": [],
                "deletes": [str(path) for path in normalized],
                "guard_roots": normalized,
            }
        )
        self._operation_state_changed()
        self._start_timer.start(0)
        self._window.statusBar().showMessage(
            "Deleting path(s) in the background…",
            3000,
        )
        return True

    def shutdown(self) -> None:
        """Stop the filesystem child process during application shutdown."""
        if self._process.state() == QProcess.ProcessState.NotRunning:
            return
        self._process.terminate()
        if not self._process.waitForFinished(250):
            self._process.kill()

    def _install_panel_delegates(self) -> None:
        """Route existing Navigator entry points through this controller without changing their UI surfaces."""
        controller = self

        def rename_path(_panel, path: Path) -> None:
            controller.rename_path(path)

        def move_path_by_drop(_panel, source: Path, destination: Path) -> bool:
            return controller.move_path_by_drop(source, destination)

        def delete_path(_panel, path: Path) -> None:
            controller.delete_path(path)

        def delete_selected(_panel) -> bool:
            return controller.delete_selected_paths()

        self._panel._rename_path = MethodType(rename_path, self._panel)
        self._panel._move_path_by_drop = MethodType(move_path_by_drop, self._panel)
        self._panel._delete_path = MethodType(delete_path, self._panel)
        self._panel._delete_selected_path = MethodType(delete_selected, self._panel)

        try:
            self._panel._delete_shortcut.activated.disconnect()
        except (RuntimeError, TypeError):
            pass
        self._panel._delete_shortcut.activated.connect(self.delete_selected_paths)

    def _try_start_next(self) -> None:
        """Start the next request only after autosave writers touching its paths have drained."""
        if self._process.state() != QProcess.ProcessState.NotRunning:
            return
        if self._active_request is not None:
            return
        if not self._queue:
            self._operation_state_changed()
            return

        request = self._queue[0]
        roots = request.get("guard_roots", [])
        autosave = getattr(self._window, "_document_autosave_controller", None)
        if autosave is not None and autosave.has_pending_writes_under(roots):
            self._start_timer.start(self._AUTOSAVE_DRAIN_POLL_MS)
            return

        self._active_request = self._queue.popleft()
        payload = {
            "moves": self._active_request.get("moves", []),
            "deletes": self._active_request.get("deletes", []),
        }
        self._active_payload = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._process.setProgram(sys.executable)
        self._process.setArguments(["-m", self._WORKER_MODULE])
        self._process.start()

    def _send_active_request(self) -> None:
        """Send one JSON request after QProcess reports that it started."""
        if not self._active_payload:
            return
        self._process.write(self._active_payload)
        self._process.closeWriteChannel()

    def _on_process_finished(self, _exit_code: int, _exit_status) -> None:
        """Publish successful filesystem changes on the GUI thread and report failures."""
        stdout = bytes(self._process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        stderr = bytes(self._process.readAllStandardError()).decode(
            "utf-8", errors="replace"
        )
        try:
            result = json.loads(stdout or "{}")
        except json.JSONDecodeError:
            result = {"moves": [], "deletes": [], "worker_error": stderr or stdout}

        active = self._active_request or {}
        guard_roots = list(active.get("guard_roots", []))
        errors: list[str] = []

        for item in result.get("moves", []) if isinstance(result, dict) else []:
            if not isinstance(item, dict):
                continue
            source = Path(str(item.get("source", ""))).expanduser().resolve(strict=False)
            destination = Path(str(item.get("destination", ""))).expanduser().resolve(strict=False)
            if bool(item.get("success")):
                self._complete_move(source, destination)
            else:
                errors.append(str(item.get("error") or f"Could not move {source}"))

        requested_deletes = {
            Path(value).expanduser().resolve(strict=False)
            for value in active.get("deletes", [])
        }
        successful_deletes: set[Path] = set()
        failed_deletes: list[Path] = []
        for item in result.get("deletes", []) if isinstance(result, dict) else []:
            if not isinstance(item, dict):
                continue
            path = Path(str(item.get("path", ""))).expanduser().resolve(strict=False)
            if bool(item.get("success")):
                successful_deletes.add(path)
                self._complete_delete(path)
            else:
                failed_deletes.append(path)
                errors.append(str(item.get("error") or f"Could not delete {path}"))

        worker_error = result.get("worker_error") if isinstance(result, dict) else None
        if worker_error:
            errors.append(str(worker_error))

        failed_delete_set = set(failed_deletes) | (requested_deletes - successful_deletes)
        maintenance = self._reference_maintenance_controller()
        if failed_delete_set and maintenance is not None:
            maintenance.cancel_delete_reference_cleanup(failed_delete_set)

        self._unblock_autosave(guard_roots)
        self._active_request = None
        self._active_payload = b""
        self._operation_state_changed()

        if errors:
            QMessageBox.critical(
                self._panel,
                "File operation",
                "\n\n".join(errors[:8]),
            )
            self._refresh_preview_after_failure()

        if self._queue:
            self._start_timer.start(0)
        elif not errors:
            self._window.statusBar().showMessage(
                "Background file operation finished.",
                3000,
            )

    def _on_process_error(self, _error) -> None:
        """Recover UI/autosave state if the filesystem child process cannot run."""
        if self._process.state() != QProcess.ProcessState.NotRunning:
            return
        active = self._active_request or {}
        roots = list(active.get("guard_roots", []))
        deletes = [Path(value) for value in active.get("deletes", [])]
        maintenance = self._reference_maintenance_controller()
        if deletes and maintenance is not None:
            maintenance.cancel_delete_reference_cleanup(deletes)
        self._unblock_autosave(roots)
        self._active_request = None
        self._active_payload = b""
        self._operation_state_changed()
        QMessageBox.critical(
            self._panel,
            "File operation",
            "Background filesystem operation could not start.",
        )
        self._refresh_preview_after_failure()
        if self._queue:
            self._start_timer.start(0)

    def _complete_move(self, old_path: Path, new_path: Path) -> None:
        """Publish one completed move through the Navigator's existing signals/state."""
        self._panel._expanded_paths = {
            self._panel._renamed_state_path(value, old_path, new_path)
            for value in self._panel._expanded_paths
        }
        self._panel._proxy_model.invalidateFilter()
        self._panel.path_renamed.emit(str(old_path), str(new_path))
        self._panel.select_path(new_path, force_reveal=True)
        self._panel.state_changed.emit()

    def _complete_delete(self, path: Path) -> None:
        """Publish one completed delete through the Navigator's existing signals/state."""
        self._panel._expanded_paths = {
            value
            for value in self._panel._expanded_paths
            if not self._same_or_child(Path(value), path)
        }
        self._panel._proxy_model.invalidateFilter()
        self._panel.path_deleted.emit(str(path))
        self._panel.state_changed.emit()

    def _selected_paths(self, fallback: Path | None = None) -> list[Path]:
        """Return selected existing Navigator paths collapsed to their top-level roots."""
        paths: list[Path] = []
        selection = self._panel._tree.selectionModel()
        indexes = selection.selectedRows(0) if selection is not None else []
        for index in indexes:
            text = self._panel._path_for_view_index(index)
            if not text:
                continue
            try:
                candidate = Path(text).expanduser().resolve(strict=False)
            except (OSError, TypeError, ValueError):
                continue
            if candidate != self._panel._root_path and candidate.exists():
                paths.append(candidate)
        if not paths and fallback is not None:
            try:
                candidate = Path(fallback).expanduser().resolve(strict=False)
            except (OSError, TypeError, ValueError):
                candidate = None
            if (
                candidate is not None
                and candidate != self._panel._root_path
                and candidate.exists()
            ):
                paths.append(candidate)
        if not paths:
            selected = self._panel.selected_path()
            if selected:
                candidate = Path(selected).expanduser().resolve(strict=False)
                if candidate != self._panel._root_path and candidate.exists():
                    paths.append(candidate)
        return self._top_level_paths(paths)

    @classmethod
    def _top_level_paths(cls, paths) -> list[Path]:
        """Deduplicate paths and drop descendants whose parent is already selected."""
        unique = sorted(
            {
                Path(path).expanduser().resolve(strict=False)
                for path in paths
                if path is not None
            },
            key=lambda value: len(value.parts),
        )
        result: list[Path] = []
        for path in unique:
            if any(cls._same_or_child(path, parent) for parent in result):
                continue
            result.append(path)
        return result

    def _workspace_resolver(self) -> WorkspaceReferenceResolver:
        """Return a resolver rooted at the configured source/search workspace."""
        return WorkspaceReferenceResolver(
            self._window._app_settings.search_default_path
        )

    def _reference_maintenance_controller(self):
        """Return the paired reference-maintenance controller when initialized."""
        return getattr(
            self._window,
            "_workspace_reference_maintenance_controller",
            None,
        )

    def _block_autosave(self, paths) -> None:
        """Prevent new autosaves under paths awaiting filesystem mutation."""
        autosave = getattr(self._window, "_document_autosave_controller", None)
        if autosave is not None:
            autosave.block_paths_under(paths)

    def _unblock_autosave(self, paths) -> None:
        """Release autosave guards after the filesystem and GUI state agree."""
        autosave = getattr(self._window, "_document_autosave_controller", None)
        if autosave is not None:
            autosave.unblock_paths_under(paths)

    def _operation_state_changed(self) -> None:
        """Disable explicit Save only while a path mutation could target stale paths."""
        save_action = getattr(self._window, "_save_action", None)
        if save_action is None:
            return
        if self.has_pending_work:
            save_action.setEnabled(False)
            return
        try:
            save_action.setEnabled(self._editor_panel.is_current_modified())
        except (AttributeError, RuntimeError):
            save_action.setEnabled(True)

    def _configure_process_environment(self) -> None:
        """Expose the project src root to the standalone filesystem worker."""
        environment = QProcessEnvironment.systemEnvironment()
        src_root = str(
            (Path(self._window._app_settings.project_root) / "src")
            .expanduser()
            .resolve(strict=False)
        )
        existing = environment.value("PYTHONPATH")
        environment.insert(
            "PYTHONPATH",
            src_root + (os.pathsep + existing if existing else ""),
        )
        self._process.setProcessEnvironment(environment)

    def _refresh_preview_after_failure(self) -> None:
        """Resume current preview state when a pre-move renderer stop is followed by failure."""
        refresh = getattr(self._window, "_refresh_current_preview", None)
        if callable(refresh):
            try:
                refresh(immediate=True)
            except (RuntimeError, TypeError):
                pass

    @staticmethod
    def _same_or_child(candidate: Path, parent: Path) -> bool:
        """Return whether candidate is parent or one of its descendants."""
        candidate = Path(candidate).expanduser().resolve(strict=False)
        parent = Path(parent).expanduser().resolve(strict=False)
        if candidate == parent:
            return True
        try:
            candidate.relative_to(parent)
            return True
        except ValueError:
            return False
