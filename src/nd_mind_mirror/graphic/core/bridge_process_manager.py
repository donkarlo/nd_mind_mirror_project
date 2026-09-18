from __future__ import annotations

from pathlib import Path
import socket
import sys

from PySide6.QtCore import QIODevice, QObject, QProcess, QProcessEnvironment
from PySide6.QtWidgets import QApplication

from nd_mind_mirror.graphic.core.bridge_process_registry import (
    GraphicBridgeProcessRegistry,
)


class GraphicBridgeProcessManager(QObject):
    """Own or adopt one canonical local iPad bridge for the application."""

    _process: QProcess | None = None
    _owns_process = False
    _cleanup_performed = False
    _external_bridge_detected = False

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        workspace_root: str | Path | None = None,
    ) -> None:
        super().__init__(parent)
        self._project_root = Path(__file__).resolve().parents[4]
        self._workspace_root = (
            Path(workspace_root).expanduser().resolve()
            if workspace_root not in (None, "")
            else (Path.home() / "Dropbox" / "repo").resolve()
        )
        self._log_path = (
            Path.home()
            / "Desktop"
            / "repo"
            / "data"
            / "nd_mind_mirror_project"
            / "logs"
            / "graphic_bridge_process.log"
        )
        self._process_registry = GraphicBridgeProcessRegistry()

    @classmethod
    def bridge_is_running(
        cls,
        host: str = "127.0.0.1",
        port: int = 8766,
    ) -> bool:
        """Return whether the canonical bridge HTTP port is accepting connections."""
        try:
            with socket.create_connection((host, int(port)), timeout=0.08):
                return True
        except OSError:
            return False

    @classmethod
    def managed_bridge_is_running(cls) -> bool:
        """Return whether this application owns or has adopted one live bridge."""
        process = cls._process
        if process is not None and process.state() != QProcess.ProcessState.NotRunning:
            return True
        return bool(cls._external_bridge_detected)

    def start_if_needed(self) -> bool:
        """Adopt a healthy bridge or start one only after stale cleanup is necessary."""
        if self._adopt_external_bridge_if_running():
            return True

        process = type(self)._process
        if (
            process is not None
            and process.state() != QProcess.ProcessState.NotRunning
        ):
            return True

        # Cleanup is intentionally delayed until the canonical endpoint is
        # unreachable. A healthy bridge launched by ND Control Panel is an
        # external owner and must never be terminated as a stale process.
        self._cleanup_stale_bridges_once()

        # A bridge may have appeared while stale cleanup was running. Adopt it
        # instead of racing it with a second process.
        if self._adopt_external_bridge_if_running():
            return True

        return self._start_owned_bridge()

    def stop(self) -> None:
        """Stop only the bridge process created by this Mind Mirror instance."""
        process = type(self)._process
        if not type(self)._owns_process or process is None:
            return
        if process.state() != QProcess.ProcessState.NotRunning:
            process.terminate()
            if not process.waitForFinished(1200):
                process.kill()
                process.waitForFinished(700)
        type(self)._process = None
        type(self)._owns_process = False
        type(self)._external_bridge_detected = False

    def _adopt_external_bridge_if_running(self) -> bool:
        """Record a healthy canonical bridge without taking ownership of it."""
        if not self.bridge_is_running():
            type(self)._external_bridge_detected = False
            return False
        type(self)._external_bridge_detected = True
        return True

    def _start_owned_bridge(self) -> bool:
        """Start the canonical bridge as a child owned by Mind Mirror."""
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        application = QApplication.instance()
        process = QProcess(application)
        environment = QProcessEnvironment.systemEnvironment()
        src_root = str(self._project_root / "src")
        existing_pythonpath = environment.value("PYTHONPATH", "")
        environment.insert(
            "PYTHONPATH",
            src_root if not existing_pythonpath else f"{src_root}:{existing_pythonpath}",
        )
        environment.insert("LANG", "C.UTF-8")
        environment.insert("LC_ALL", "C.UTF-8")
        process.setProcessEnvironment(environment)
        process.setWorkingDirectory(str(self._project_root))
        process.setProgram(sys.executable)
        process.setArguments(
            [
                "-m",
                "nd_mind_mirror.graphic.bridge",
                "--workspace",
                str(self._workspace_root),
            ]
        )
        process.setStandardOutputFile(
            str(self._log_path),
            QIODevice.OpenModeFlag.Append,
        )
        process.setStandardErrorFile(
            str(self._log_path),
            QIODevice.OpenModeFlag.Append,
        )
        process.start()
        type(self)._process = process
        type(self)._owns_process = bool(process.waitForStarted(350))
        type(self)._external_bridge_detected = False
        return type(self)._owns_process or self.bridge_is_running()

    def _cleanup_stale_bridges_once(self) -> None:
        """Remove orphaned bridge processes only after no healthy endpoint exists."""
        cls = type(self)
        if cls._cleanup_performed:
            return
        cls._cleanup_performed = True
        self._process_registry.terminate_all()
