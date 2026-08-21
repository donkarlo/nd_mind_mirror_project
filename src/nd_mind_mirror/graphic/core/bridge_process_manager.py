from __future__ import annotations

from pathlib import Path
import socket
import sys

from PySide6.QtCore import QIODevice, QObject, QProcess, QProcessEnvironment


class GraphicBridgeProcessManager(QObject):
    """Start the local graphic bridge with Mind Mirror when needed."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process: QProcess | None = None
        self._owns_process = False
        self._project_root = Path(__file__).resolve().parents[4]
        self._log_path = (
            Path.home()
            / "Desktop"
            / "repo"
            / "data"
            / "nd_mind_mirror_project"
            / "logs"
            / "graphic_bridge_process.log"
        )

    @staticmethod
    def _port_is_open(host: str = "127.0.0.1", port: int = 8766) -> bool:
        try:
            with socket.create_connection((host, port), timeout=0.10):
                return True
        except OSError:
            return False

    def start_if_needed(self) -> bool:
        if self._port_is_open():
            return True
        if self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning:
            return True

        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        process = QProcess(self)
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
        process.setArguments(["-m", "nd_mind_mirror.graphic.bridge"])
        process.setStandardOutputFile(str(self._log_path), QIODevice.OpenModeFlag.Append)
        process.setStandardErrorFile(str(self._log_path), QIODevice.OpenModeFlag.Append)
        process.start()
        self._process = process
        self._owns_process = bool(process.waitForStarted(1800))
        return self._owns_process or self._port_is_open()

    def stop(self) -> None:
        process = self._process
        if not self._owns_process or process is None:
            return
        if process.state() == QProcess.ProcessState.NotRunning:
            return
        process.terminate()
        if not process.waitForFinished(1200):
            process.kill()
            process.waitForFinished(700)
