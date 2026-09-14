"""Asynchronous cached TikZ previews for LaTeX Visual mode."""

from __future__ import annotations

from pathlib import Path
import re
from threading import Lock

from PySide6.QtCore import QObject, QThreadPool, Signal
from PySide6.QtGui import QImage

from nd_mind_mirror.core.workspace.path.workspace_reference_resolver import (
    WorkspaceReferenceResolver,
)
from nd_mind_mirror.graphic.tikz.bridge.renderer import TikZRenderer
from nd_mind_mirror.ui.editor.latex.tikz_visual_preview_render_task import (
    TikZVisualPreviewRenderTask,
)


class TikZVisualPreviewService(QObject):
    """Resolve TikZ inputs immediately and render cache misses in the background."""

    preview_ready = Signal(str, str, object)

    _INPUT = re.compile(
        r"^\s*\\(?:input|include)\s*\{(?P<target>[^}]+)\}\s*(?:%.*)?$"
    )

    def __init__(
        self,
        workspace_root: str | Path,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._workspace_root = Path(workspace_root).expanduser().resolve()
        self._resolver = WorkspaceReferenceResolver(self._workspace_root)
        self._renderer = TikZRenderer(self._workspace_root)
        self._pool = QThreadPool.globalInstance()
        self._cache: dict[tuple[Path, int, int], QImage] = {}
        self._pending: set[tuple[Path, int, int]] = set()
        self._failed: set[tuple[Path, int, int]] = set()
        self._lock = Lock()

    def preview_for_input(
        self,
        raw: str,
        referring_file: str | Path | None,
    ) -> QImage | None:
        request = self._resolve_request(raw, referring_file)
        if request is None:
            return None
        target, source, key, referring_path = request

        with self._lock:
            cached = self._cache.get(key)
            if cached is not None and not cached.isNull():
                return QImage(cached)
            if key in self._pending or key in self._failed:
                return None
            self._pending.add(key)

        self._pool.start(
            TikZVisualPreviewRenderTask(
                renderer=self._renderer,
                source=source,
                target=target,
                cache_key=key,
                referring_file=referring_path,
                raw_input=raw,
                completion=self._complete,
            )
        )
        return None

    def _resolve_request(
        self,
        raw: str,
        referring_file: str | Path | None,
    ) -> tuple[Path, str, tuple[Path, int, int], Path] | None:
        if referring_file in (None, ""):
            return None
        match = self._INPUT.match(raw.strip())
        if match is None:
            return None
        referring_path = Path(referring_file).expanduser().resolve()
        target = self._resolver.resolve(
            match.group("target"),
            referring_path,
            command="input",
            require_exists=True,
        )
        if target is None or not target.is_file():
            return None
        try:
            source = target.read_text(encoding="utf-8")
            if "\\begin{tikzpicture}" not in source:
                return None
            stat = target.stat()
        except OSError:
            return None
        return (
            target,
            source,
            (target, stat.st_mtime_ns, stat.st_size),
            referring_path,
        )

    def _complete(
        self,
        key: tuple[Path, int, int],
        referring_file: Path,
        raw_input: str,
        image: QImage | None,
        error: str | None,
    ) -> None:
        with self._lock:
            self._pending.discard(key)
            if error is not None or image is None or image.isNull():
                self._failed.add(key)
                return
            target = key[0]
            self._cache = {
                cache_key: cached
                for cache_key, cached in self._cache.items()
                if cache_key[0] != target
            }
            self._failed = {
                failed_key
                for failed_key in self._failed
                if failed_key[0] != target
            }
            stored = QImage(image)
            self._cache[key] = stored

        self.preview_ready.emit(
            str(referring_file),
            raw_input,
            QImage(stored),
        )
