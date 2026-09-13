"""Own the in-process TikZ WebSocket bridge for one Mind Mirror desktop session."""

from __future__ import annotations

from pathlib import Path
from threading import Thread

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication
import uvicorn

from nd_mind_mirror.graphic.tikz.bridge.renderer import TikZRenderer
from nd_mind_mirror.graphic.tikz.bridge.server import TikZBridgeServer
from nd_mind_mirror.graphic.tikz.bridge.workspace import TikZWorkspace


class TikZBridgeSessionController(QObject):
    """Run the separate TikZ bridge in a daemon thread without touching image bridge state."""

    def __init__(
        self,
        *,
        workspace_root: str | Path,
        host: str = "0.0.0.0",
        port: int = 8765,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._workspace_root = Path(workspace_root).expanduser().resolve()
        self._host = host
        self._port = int(port)
        self._server: uvicorn.Server | None = None
        self._thread: Thread | None = None
        application = QApplication.instance()
        if application is not None:
            application.aboutToQuit.connect(self.stop)

    def start(self) -> bool:
        """Start the TikZ bridge once for this desktop application session."""
        if self._thread is not None and self._thread.is_alive():
            return True
        workspace = TikZWorkspace(self._workspace_root)
        renderer = TikZRenderer(workspace.root)
        bridge = TikZBridgeServer(workspace, renderer)
        config = uvicorn.Config(
            bridge.app,
            host=self._host,
            port=self._port,
            log_level="warning",
            access_log=False,
        )
        self._server = uvicorn.Server(config)
        self._thread = Thread(
            target=self._server.run,
            name="nd-mind-mirror-tikz-bridge",
            daemon=True,
        )
        self._thread.start()
        return True

    def stop(self) -> None:
        """Request bridge shutdown without affecting the raster-image bridge."""
        if self._server is not None:
            self._server.should_exit = True
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.5)
        self._thread = None
        self._server = None
