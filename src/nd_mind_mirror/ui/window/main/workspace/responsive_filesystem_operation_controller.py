"""Keep delete-reference discovery off the Qt GUI thread."""

from __future__ import annotations

import json
import os
import sys
from collections import deque
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment
from PySide6.QtWidgets import QDialog, QMessageBox

from nd_mind_mirror.core.workspace.path.workspace_reference_resolver import (
    ReferenceOccurrence,
    WorkspaceReferenceResolver,
)
from nd_mind_mirror.ui.window.main.workspace.filesystem_operation_controller import (
    WorkspaceFilesystemOperationController,
)
from nd_mind_mirror.ui.window.main.workspace.reference_delete_dialog import (
    ReferenceDeleteDialog,
)


class ResponsiveWorkspaceFilesystemOperationController(
    WorkspaceFilesystemOperationController
):
    """Run delete reference preflight in a child process before existing dialogs."""

    _REFERENCE_SCAN_WORKER_MODULE = (
        "nd_mind_mirror.core.workspace.operation.reference_usage_scan_worker"
    )

    def __init__(self, window, parent=None) -> None:
        """Create the filesystem controller and its independent read-only scan worker."""
        super().__init__(window, parent)
        self._reference_scan_queue: deque[dict[str, object]] = deque()
        self._active_reference_scan: dict[str, object] | None = None
        self._reference_scan_payload = b""

        self._reference_scan_process = QProcess(self)
        self._reference_scan_process.started.connect(
            self._send_active_reference_scan
        )
        self._reference_scan_process.finished.connect(
            self._on_reference_scan_finished
        )
        self._reference_scan_process.errorOccurred.connect(
            self._on_reference_scan_error
        )
        self._configure_reference_scan_environment()

    def delete_path(self, path: Path) -> bool:
        """Queue the expensive single-path reference scan and return immediately."""
        target = Path(path).expanduser().resolve(strict=False)
        if target == self._panel._root_path or not target.exists():
            return False
        self._queue_reference_scan("single", [target])
        return True

    def delete_selected_paths(self) -> bool:
        """Keep multi-delete choice synchronous but scan references in the background."""
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
        if decision == QMessageBox.StandardButton.No:
            self.request_deletions(paths)
            return True

        self._queue_reference_scan("multiple", paths)
        return True

    def shutdown(self) -> None:
        """Stop both the read-only scan worker and the filesystem mutation worker."""
        if self._reference_scan_process.state() != QProcess.ProcessState.NotRunning:
            self._reference_scan_process.terminate()
            if not self._reference_scan_process.waitForFinished(250):
                self._reference_scan_process.kill()
        super().shutdown()

    def _queue_reference_scan(self, mode: str, paths: list[Path]) -> None:
        """Serialize one reference-preflight request without blocking editor interaction."""
        normalized = self._top_level_paths(paths)
        if not normalized:
            return
        self._reference_scan_queue.append(
            {
                "mode": str(mode),
                "paths": normalized,
            }
        )
        self._window.statusBar().showMessage(
            "Searching file references in the background…",
            3000,
        )
        self._start_next_reference_scan()

    def _start_next_reference_scan(self) -> None:
        """Start the next queued reference scan when its child process is idle."""
        if self._reference_scan_process.state() != QProcess.ProcessState.NotRunning:
            return
        if self._active_reference_scan is not None or not self._reference_scan_queue:
            return

        self._active_reference_scan = self._reference_scan_queue.popleft()
        paths = list(self._active_reference_scan.get("paths", []))
        resolver = self._workspace_resolver()
        payload = {
            "workspace_root": str(resolver.default_path or self._panel._root_path),
            "targets": [str(path) for path in paths],
            "ignore_file_path": self._optional_path_text(
                self._window._app_settings.search_ignore_file_path
            ),
        }
        self._reference_scan_payload = json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8")
        self._reference_scan_process.setProgram(sys.executable)
        self._reference_scan_process.setArguments(
            ["-m", self._REFERENCE_SCAN_WORKER_MODULE]
        )
        self._reference_scan_process.start()

    def _send_active_reference_scan(self) -> None:
        """Send the active JSON request once the scan child process has started."""
        if not self._reference_scan_payload:
            return
        self._reference_scan_process.write(self._reference_scan_payload)
        self._reference_scan_process.closeWriteChannel()

    def _on_reference_scan_finished(self, _exit_code: int, _exit_status) -> None:
        """Show the existing dialogs only after background discovery has completed."""
        stdout = bytes(self._reference_scan_process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        stderr = bytes(self._reference_scan_process.readAllStandardError()).decode(
            "utf-8", errors="replace"
        )
        active = self._active_reference_scan
        self._active_reference_scan = None
        self._reference_scan_payload = b""

        try:
            result = json.loads(stdout or "{}")
        except json.JSONDecodeError:
            result = {
                "usages_by_target": {},
                "errors": [stderr or stdout or "invalid reference scan output"],
            }

        errors = result.get("errors", []) if isinstance(result, dict) else []
        if errors:
            QMessageBox.critical(
                self._panel,
                "Delete — reference scan",
                "Could not finish the reference scan.\n\n"
                + "\n".join(str(item) for item in errors[:8]),
            )
        elif active is not None:
            usages_by_target = self._deserialize_usages_by_target(result)
            mode = str(active.get("mode", "single"))
            paths = [
                Path(path).expanduser().resolve(strict=False)
                for path in active.get("paths", [])
            ]
            if mode == "multiple":
                self._continue_multiple_delete(paths, usages_by_target)
            elif paths:
                self._continue_single_delete(paths[0], usages_by_target)

        self._start_next_reference_scan()

    def _on_reference_scan_error(self, _error) -> None:
        """Recover from scan-process startup/runtime failures without deleting anything."""
        if self._reference_scan_process.state() != QProcess.ProcessState.NotRunning:
            return
        self._active_reference_scan = None
        self._reference_scan_payload = b""
        QMessageBox.critical(
            self._panel,
            "Delete — reference scan",
            "Background reference scan could not start.",
        )
        self._start_next_reference_scan()

    def _continue_single_delete(
        self,
        target: Path,
        usages_by_target: dict[Path, list[ReferenceOccurrence]],
    ) -> None:
        """Preserve the existing usage dialog and delete confirmation after scanning."""
        if not target.exists():
            self._window.statusBar().showMessage(
                f"Delete target no longer exists: {target}",
                5000,
            )
            return

        usages = usages_by_target.get(target, [])
        resolver = self._workspace_resolver()
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
                return

        kind = "folder" if target.is_dir() else "file"
        decision = QMessageBox.warning(
            self._panel,
            "Delete",
            f"Delete this {kind} permanently?\n\n{target}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if decision != QMessageBox.StandardButton.Yes:
            return

        maintenance = self._reference_maintenance_controller()
        if maintenance is not None:
            maintenance.register_delete_reference_cleanup(
                {target: usages},
                resolver,
            )
        accepted = self.request_deletions([target])
        if not accepted and maintenance is not None:
            maintenance.cancel_delete_reference_cleanup([target])

    def _continue_multiple_delete(
        self,
        paths: list[Path],
        usages_by_target: dict[Path, list[ReferenceOccurrence]],
    ) -> None:
        """Register precomputed multi-delete cleanup and queue the existing delete worker."""
        existing = [path for path in paths if path.exists()]
        if not existing:
            return
        resolver = self._workspace_resolver()
        maintenance = self._reference_maintenance_controller()
        if maintenance is not None:
            maintenance.register_delete_reference_cleanup(
                {path: usages_by_target.get(path, []) for path in existing},
                resolver,
            )
        accepted = self.request_deletions(existing)
        if not accepted and maintenance is not None:
            maintenance.cancel_delete_reference_cleanup(existing)

    @staticmethod
    def _deserialize_usages_by_target(
        result: object,
    ) -> dict[Path, list[ReferenceOccurrence]]:
        """Rebuild domain occurrences from the child process JSON response."""
        if not isinstance(result, dict):
            return {}
        raw_mapping = result.get("usages_by_target")
        if not isinstance(raw_mapping, dict):
            return {}

        output: dict[Path, list[ReferenceOccurrence]] = {}
        for raw_target, raw_usages in raw_mapping.items():
            try:
                target = Path(str(raw_target)).expanduser().resolve(strict=False)
            except (OSError, TypeError, ValueError):
                continue
            usages: list[ReferenceOccurrence] = []
            if isinstance(raw_usages, list):
                for item in raw_usages:
                    occurrence = ResponsiveWorkspaceFilesystemOperationController._deserialize_occurrence(
                        item
                    )
                    if occurrence is not None:
                        usages.append(occurrence)
            output[target] = usages
        return output

    @staticmethod
    def _deserialize_occurrence(item: object) -> ReferenceOccurrence | None:
        """Rebuild one ReferenceOccurrence from JSON-safe worker data."""
        if not isinstance(item, dict):
            return None
        try:
            target_text = str(item.get("target_path", ""))
            target_path = (
                Path(target_text).expanduser().resolve(strict=False)
                if target_text
                else None
            )
            return ReferenceOccurrence(
                str(item["command"]),
                str(item["raw_target"]),
                target_path,
                int(item["target_start"]),
                int(item["target_end"]),
                int(item["command_start"]),
                int(item["command_end"]),
                int(item["click_start"]),
                int(item["click_end"]),
                int(item["line"]),
                int(item["column"]),
                Path(str(item["referring_file"])).expanduser().resolve(strict=False),
            )
        except (KeyError, OSError, TypeError, ValueError):
            return None

    def _configure_reference_scan_environment(self) -> None:
        """Expose project sources to the standalone reference-scan worker."""
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
        self._reference_scan_process.setProcessEnvironment(environment)

    @staticmethod
    def _optional_path_text(value: object) -> str:
        """Return an optional path as JSON-safe text."""
        if value in (None, ""):
            return ""
        return str(Path(str(value)).expanduser().resolve(strict=False))
