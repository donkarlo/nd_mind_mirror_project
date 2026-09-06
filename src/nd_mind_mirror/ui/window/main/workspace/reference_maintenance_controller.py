"""Keep path-reference maintenance out of the Qt GUI thread after file operations."""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer

from nd_mind_mirror.core.workspace.path.path_reference_updater import PathReferenceUpdater
from nd_mind_mirror.core.workspace.path.workspace_reference_resolver import (
    ReferenceOccurrence,
    WorkspaceReferenceResolver,
)


class WorkspaceReferenceMaintenanceController(QObject):
    """Preserve synchronous preflight while running repository maintenance in a child process."""

    _WORKER_MODULE = (
        "nd_mind_mirror.core.workspace.operation.reference_maintenance_worker"
    )
    _QUEUE_DELAY_MS = 40

    def __init__(self, window, parent=None) -> None:
        """Replace blocking MainWindow path-maintenance slots with queued process-backed work."""
        super().__init__(parent)
        self._window = window
        self._panel = window._file_system_panel
        self._editor_panel = window._editor_panel
        self._pending_moves: list[tuple[Path, Path]] = []
        self._pending_deletions: dict[Path, set[Path]] = defaultdict(set)
        self._registered_delete_cleanup: dict[
            Path,
            tuple[list[ReferenceOccurrence], WorkspaceReferenceResolver],
        ] = {}
        self._active_request: dict[str, object] | None = None
        self._active_payload = b""

        self._flush_timer = QTimer(self)
        self._flush_timer.setSingleShot(True)
        self._flush_timer.setInterval(self._QUEUE_DELAY_MS)
        self._flush_timer.timeout.connect(self._start_pending_request)

        self._index_refresh_timer = QTimer(self)
        self._index_refresh_timer.setSingleShot(True)
        self._index_refresh_timer.setInterval(80)
        self._index_refresh_timer.timeout.connect(self._rebuild_search_index)

        self._process = QProcess(self)
        self._process.started.connect(self._send_active_request)
        self._process.finished.connect(self._on_process_finished)
        self._process.errorOccurred.connect(self._on_process_error)
        self._configure_process_environment()
        self._replace_blocking_main_window_slots()

    @property
    def has_pending_work(self) -> bool:
        """Return whether reference work is queued, starting, or executing."""
        return bool(
            self._pending_moves
            or self._pending_deletions
            or self._active_request is not None
            or self._flush_timer.isActive()
            or self._process.state() != QProcess.ProcessState.NotRunning
        )

    def register_delete_reference_cleanup(
        self,
        usages_by_target: dict[Path, list[ReferenceOccurrence]],
        resolver: WorkspaceReferenceResolver,
    ) -> None:
        """Remember precomputed delete usages until each asynchronous delete succeeds."""
        for target, usages in usages_by_target.items():
            resolved = Path(target).expanduser().resolve(strict=False)
            self._registered_delete_cleanup[resolved] = (list(usages), resolver)

    def cancel_delete_reference_cleanup(self, paths) -> None:
        """Forget precomputed reference cleanup for deletes that did not complete."""
        for path in paths:
            try:
                resolved = Path(path).expanduser().resolve(strict=False)
            except (OSError, TypeError, ValueError):
                continue
            self._registered_delete_cleanup.pop(resolved, None)

    def remove_deleted_references(
        self,
        target: Path,
        usages: list[ReferenceOccurrence],
        resolver: WorkspaceReferenceResolver,
    ) -> None:
        """Update open referring files immediately and queue closed files for the worker."""
        target = Path(target).expanduser().resolve(strict=False)
        open_editors = self._open_editors_by_path()
        queued_files: set[Path] = set()

        for referring_file in sorted({usage.referring_file for usage in usages}):
            referring = Path(referring_file).expanduser().resolve(strict=False)
            if self._same_or_child(referring, target):
                continue
            editor = open_editors.get(referring)
            if editor is None:
                queued_files.add(referring)
                continue
            self._remove_reference_from_open_editor(
                editor,
                referring,
                target,
                resolver,
            )

        if queued_files:
            self._pending_deletions[target].update(queued_files)
            self._schedule_worker()
        else:
            self._index_refresh_timer.start()

    def shutdown(self) -> None:
        """Stop the child process when the owning window is shutting down."""
        if self._process.state() == QProcess.ProcessState.NotRunning:
            return
        self._process.terminate()
        if not self._process.waitForFinished(250):
            self._process.kill()

    def _replace_blocking_main_window_slots(self) -> None:
        """Keep all other path listeners but replace only the two blocking base slots."""
        try:
            self._panel.path_renamed.disconnect(self._window._on_navigator_path_renamed)
        except (RuntimeError, TypeError):
            pass
        try:
            self._panel.path_deleted.disconnect(self._window._on_navigator_path_deleted)
        except (RuntimeError, TypeError):
            pass
        self._panel.path_renamed.connect(self._on_path_renamed)
        self._panel.path_deleted.connect(self._on_path_deleted)

    def _on_path_renamed(self, old_path: str, new_path: str) -> None:
        """Remap live UI state immediately, then queue repository reference rewriting."""
        old_root = Path(old_path).expanduser().resolve(strict=False)
        new_root = Path(new_path).expanduser().resolve(strict=False)

        autosave = getattr(self._window, "_document_autosave_controller", None)
        if autosave is not None:
            autosave.remap_paths_under(old_root, new_root)

        updated_signatures: dict[Path, tuple[int, int]] = {}
        for signature_path, signature in self._window._file_signatures.items():
            try:
                relative = signature_path.relative_to(old_root)
            except ValueError:
                updated_signatures[signature_path] = signature
                continue
            updated_signatures[(new_root / relative).resolve(strict=False)] = signature
        self._window._file_signatures = updated_signatures

        self._window._recent_file_paths = [
            (new_root / path.relative_to(old_root)).resolve(strict=False)
            if self._same_or_child(path, old_root)
            else path
            for path in self._window._recent_file_paths
        ]

        self._editor_panel.rename_paths_under(old_root, new_root)
        self._rewrite_open_move_references(old_root, new_root)

        current = self._editor_panel.current_path()
        if current is not None:
            self._panel.select_path(current)

        self._pending_moves.append((old_root, new_root))
        self._schedule_worker()
        self._window._save_session()
        self._window.statusBar().showMessage(
            "Path moved; updating repository references in the background…",
            3000,
        )

    def _on_path_deleted(self, path: str) -> None:
        """Apply lightweight delete UI state and schedule any registered reference cleanup."""
        deleted_root = Path(path).expanduser().resolve(strict=False)

        autosave = getattr(self._window, "_document_autosave_controller", None)
        if autosave is not None:
            autosave.discard_paths_under(deleted_root)

        self._window._file_signatures = {
            candidate: signature
            for candidate, signature in self._window._file_signatures.items()
            if not self._same_or_child(candidate, deleted_root)
        }
        self._window._recent_file_paths = [
            candidate
            for candidate in self._window._recent_file_paths
            if not self._same_or_child(candidate, deleted_root)
        ]

        self._editor_panel.close_paths_under(deleted_root)
        current = self._editor_panel.current_path()
        if current is not None:
            self._panel.select_path(current)
        else:
            self._window._preview_panel.show_message(
                "Open a LaTeX or Markdown file to render its preview."
            )

        cleanup = self._registered_delete_cleanup.pop(deleted_root, None)
        if cleanup is not None:
            usages, resolver = cleanup
            if usages:
                self.remove_deleted_references(
                    deleted_root,
                    usages,
                    resolver,
                )
            else:
                self._index_refresh_timer.start()
        else:
            self._index_refresh_timer.start()

        self._window._save_session()

    def _rewrite_open_move_references(self, old_root: Path, new_root: Path) -> None:
        """Keep open editor buffers race-free while closed files are handled by the worker."""
        workspace_root = Path(
            self._window._app_settings.search_default_path
        ).expanduser().resolve(strict=False)
        for editor, referring_file in list(self._editor_panel._paths.items()):
            path = Path(referring_file).expanduser().resolve(strict=False)
            try:
                source = editor.toPlainText()
            except (AttributeError, RuntimeError):
                continue
            updated = PathReferenceUpdater.rewrite_source_for_mappings(
                source,
                referring_file=path,
                workspace_root=workspace_root,
                mappings=[(old_root, new_root)],
            )
            if updated == source:
                continue
            self._write_open_editor_content(editor, path, updated)

    def _remove_reference_from_open_editor(
        self,
        editor,
        referring_file: Path,
        target: Path,
        resolver: WorkspaceReferenceResolver,
    ) -> None:
        """Remove one deleted target from an open editor before background work begins."""
        try:
            source = editor.toPlainText()
        except (AttributeError, RuntimeError):
            return
        updated = resolver.remove_references(source, referring_file, target)
        if updated == source:
            return
        self._write_open_editor_content(editor, referring_file, updated)

    def _write_open_editor_content(self, editor, path: Path, content: str) -> None:
        """Persist a deterministic reference edit and keep the corresponding editor synchronized."""
        try:
            path.write_text(content, encoding="utf-8")
        except OSError:
            return
        try:
            editor.set_content(content)
        except (AttributeError, RuntimeError):
            pass
        try:
            self._window._remember_file_signature(path)
        except (AttributeError, RuntimeError, OSError):
            pass

    def _schedule_worker(self) -> None:
        """Coalesce consecutive move/delete events so a batch causes one repository scan."""
        if self._process.state() == QProcess.ProcessState.NotRunning:
            self._flush_timer.start()

    def _start_pending_request(self) -> None:
        """Start one child process for all currently queued reference work."""
        if self._process.state() != QProcess.ProcessState.NotRunning:
            return
        if not self._pending_moves and not self._pending_deletions:
            self._index_refresh_timer.start()
            return

        request = {
            "workspace_root": str(
                Path(self._window._app_settings.search_default_path)
                .expanduser()
                .resolve(strict=False)
            ),
            "ignore_file_path": self._optional_path_text(
                self._window._app_settings.search_ignore_file_path
            ),
            "moves": [
                {"old": str(old_path), "new": str(new_path)}
                for old_path, new_path in self._pending_moves
            ],
            "deletions": [
                {
                    "target": str(target),
                    "files": [str(path) for path in sorted(files)],
                }
                for target, files in self._pending_deletions.items()
            ],
            "exclude_files": [str(path) for path in sorted(self._open_paths())],
        }
        self._pending_moves.clear()
        self._pending_deletions.clear()
        self._active_request = request
        self._active_payload = json.dumps(request, ensure_ascii=False).encode("utf-8")
        self._process.setProgram(sys.executable)
        self._process.setArguments(["-m", self._WORKER_MODULE])
        self._process.start()

    def _send_active_request(self) -> None:
        """Send the queued JSON request only after QProcess has started."""
        if not self._active_payload:
            return
        self._process.write(self._active_payload)
        self._process.closeWriteChannel()

    def _on_process_finished(self, _exit_code: int, _exit_status) -> None:
        """Merge worker results into editors opened during work and start the next batch."""
        stdout = bytes(self._process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        stderr = bytes(self._process.readAllStandardError()).decode(
            "utf-8", errors="replace"
        )
        try:
            result = json.loads(stdout or "{}")
        except json.JSONDecodeError:
            result = {
                "changed_files": [],
                "errors": [stderr or stdout or "invalid worker output"],
            }

        request = self._active_request or {}
        self._merge_request_into_open_editors(request)
        self._active_request = None
        self._active_payload = b""
        self._rebuild_search_index()

        changed = result.get("changed_files", []) if isinstance(result, dict) else []
        errors = result.get("errors", []) if isinstance(result, dict) else []
        if errors:
            self._window.statusBar().showMessage(
                f"Reference maintenance finished with {len(errors)} error(s).",
                7000,
            )
        elif changed:
            self._window.statusBar().showMessage(
                f"Updated {len(changed)} reference file(s) in the background.",
                5000,
            )

        if self._pending_moves or self._pending_deletions:
            self._flush_timer.start()

    def _on_process_error(self, _error) -> None:
        """Keep the editor responsive and report a child-process startup/runtime failure."""
        if self._process.state() != QProcess.ProcessState.NotRunning:
            return
        self._active_request = None
        self._active_payload = b""
        self._window.statusBar().showMessage(
            "Background reference maintenance could not start.",
            7000,
        )
        if self._pending_moves or self._pending_deletions:
            self._flush_timer.start()

    def _merge_request_into_open_editors(self, request: dict[str, object]) -> None:
        """Apply deterministic transforms to editors opened during worker execution."""
        raw_moves = request.get("moves")
        mappings: list[tuple[Path, Path]] = []
        if isinstance(raw_moves, list):
            for item in raw_moves:
                if not isinstance(item, dict):
                    continue
                try:
                    mappings.append(
                        (
                            Path(str(item["old"])).expanduser().resolve(strict=False),
                            Path(str(item["new"])).expanduser().resolve(strict=False),
                        )
                    )
                except (KeyError, OSError, TypeError, ValueError):
                    continue

        delete_by_file: dict[Path, list[Path]] = defaultdict(list)
        raw_deletions = request.get("deletions")
        if isinstance(raw_deletions, list):
            for item in raw_deletions:
                if not isinstance(item, dict):
                    continue
                try:
                    target = Path(str(item["target"])).expanduser().resolve(strict=False)
                except (KeyError, OSError, TypeError, ValueError):
                    continue
                raw_files = item.get("files")
                if not isinstance(raw_files, list):
                    continue
                for raw_file in raw_files:
                    try:
                        path = Path(str(raw_file)).expanduser().resolve(strict=False)
                    except (OSError, TypeError, ValueError):
                        continue
                    delete_by_file[path].append(target)

        workspace_root = Path(
            self._window._app_settings.search_default_path
        ).expanduser().resolve(strict=False)
        resolver = WorkspaceReferenceResolver(workspace_root)
        for editor, raw_path in list(self._editor_panel._paths.items()):
            path = Path(raw_path).expanduser().resolve(strict=False)
            try:
                source = editor.toPlainText()
            except (AttributeError, RuntimeError):
                continue
            updated = PathReferenceUpdater.rewrite_source_for_mappings(
                source,
                referring_file=path,
                workspace_root=workspace_root,
                mappings=mappings,
            )
            for target in delete_by_file.get(path, []):
                updated = resolver.remove_references(updated, path, target)
            if updated != source:
                self._write_open_editor_content(editor, path, updated)

    def _configure_process_environment(self) -> None:
        """Expose the project src root to the standalone worker module."""
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

    def _open_editors_by_path(self) -> dict[Path, object]:
        """Return the current editor objects keyed by their resolved paths."""
        return {
            Path(path).expanduser().resolve(strict=False): editor
            for editor, path in list(self._editor_panel._paths.items())
        }

    def _open_paths(self) -> set[Path]:
        """Return paths that the worker must not mutate while they are open."""
        return set(self._open_editors_by_path())

    def _rebuild_search_index(self) -> None:
        """Refresh search once after a coalesced path-operation batch."""
        try:
            self._window._search_window.rebuild_index()
        except (AttributeError, RuntimeError):
            pass

    @staticmethod
    def _optional_path_text(value) -> str | None:
        """Serialize one optional path for the child process."""
        if value in (None, ""):
            return None
        try:
            return str(Path(value).expanduser().resolve(strict=False))
        except (OSError, TypeError, ValueError):
            return None

    @staticmethod
    def _same_or_child(candidate: Path, root: Path) -> bool:
        """Return whether candidate is root or one of its descendants."""
        candidate = Path(candidate).expanduser().resolve(strict=False)
        root = Path(root).expanduser().resolve(strict=False)
        if candidate == root:
            return True
        try:
            candidate.relative_to(root)
            return True
        except ValueError:
            return False
