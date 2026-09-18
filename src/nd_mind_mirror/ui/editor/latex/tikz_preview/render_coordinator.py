"""Shared TikZ preview cache with a fast vector path and serialized fallback."""

from __future__ import annotations

from pathlib import Path
from threading import Lock

from PySide6.QtCore import QObject, QThreadPool, Signal
from PySide6.QtGui import QImage

from nd_mind_mirror.graphic.tikz.bridge.renderer import TikZRenderer
from nd_mind_mirror.ui.editor.latex.tikz_preview.fast_tikz_preview_renderer import (
    TikZFastPreviewRenderer,
)
from nd_mind_mirror.ui.editor.latex.tikz_visual_preview_render_task import (
    TikZVisualPreviewRenderTask,
)


class TikZPreviewRenderCoordinator(QObject):
    """Share one preview cache and at most one expensive TikZ process per workspace."""

    preview_ready = Signal(str, str, object)

    _instances: dict[Path, "TikZPreviewRenderCoordinator"] = {}
    _instances_lock = Lock()

    @classmethod
    def shared(
        cls,
        workspace_root: str | Path,
    ) -> "TikZPreviewRenderCoordinator":
        root = Path(workspace_root).expanduser().resolve()
        with cls._instances_lock:
            coordinator = cls._instances.get(root)
            if coordinator is None:
                coordinator = cls(root)
                cls._instances[root] = coordinator
            return coordinator

    def __init__(self, workspace_root: str | Path) -> None:
        super().__init__(None)
        self._workspace_root = Path(workspace_root).expanduser().resolve()
        self._fast_renderer = TikZFastPreviewRenderer()
        self._fallback_renderer = TikZRenderer(self._workspace_root)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)

        self._lock = Lock()
        self._cache: dict[tuple[Path, int, int], QImage] = {}
        self._latest_image_by_target: dict[Path, QImage] = {}
        self._displayed_key_by_target: dict[Path, tuple[Path, int, int]] = {}
        self._latest_request_by_target: dict[
            Path,
            tuple[str, tuple[Path, int, int]],
        ] = {}
        self._running_key_by_target: dict[Path, tuple[Path, int, int]] = {}
        self._failed: set[tuple[Path, int, int]] = set()
        self._watchers_by_target: dict[Path, set[tuple[str, str]]] = {}

    def request(
        self,
        *,
        target: Path,
        source: str,
        key: tuple[Path, int, int],
        referring_file: Path,
        raw_input: str,
        allow_fallback: bool = True,
    ) -> QImage | None:
        """Return a preview and start LuaLaTeX only when fallback is explicitly allowed."""
        target = target.resolve()
        referring = str(referring_file.resolve())

        with self._lock:
            self._watchers_by_target.setdefault(target, set()).add(
                (referring, raw_input)
            )
            cached = self._cache.get(key)
            if cached is not None and not cached.isNull():
                return QImage(cached)

        fast = self._fast_renderer.render(source, target)
        if fast is not None and not fast.isNull():
            self._store_fast_frame(target, key, fast)
            return QImage(fast)

        with self._lock:
            fallback = self._latest_image_by_target.get(target)
            fallback_copy = (
                QImage(fallback)
                if fallback is not None and not fallback.isNull()
                else None
            )

        # Live iPad updates use this branch. A frame may remain one generation
        # behind, but no LuaLaTeX process is ever launched while strokes arrive.
        if not allow_fallback:
            return fallback_copy

        start_request: tuple[Path, str, tuple[Path, int, int]] | None = None
        with self._lock:
            if key not in self._failed:
                self._latest_request_by_target[target] = (source, key)
                if target not in self._running_key_by_target:
                    self._running_key_by_target[target] = key
                    start_request = (target, source, key)

        if start_request is not None:
            self._start_fallback_render(*start_request)
        return fallback_copy

    def _store_fast_frame(
        self,
        target: Path,
        key: tuple[Path, int, int],
        image: QImage,
    ) -> None:
        with self._lock:
            stored = QImage(image)
            self._cache = {
                cache_key: cached
                for cache_key, cached in self._cache.items()
                if cache_key[0].resolve() != target
            }
            self._cache[key] = stored
            self._latest_image_by_target[target] = stored
            self._displayed_key_by_target[target] = key
            self._failed = {
                failed_key
                for failed_key in self._failed
                if failed_key[0].resolve() != target
            }
            self._latest_request_by_target.pop(target, None)

    def _start_fallback_render(
        self,
        target: Path,
        source: str,
        key: tuple[Path, int, int],
    ) -> None:
        self._pool.start(
            TikZVisualPreviewRenderTask(
                renderer=self._fallback_renderer,
                source=source,
                target=target,
                cache_key=key,
                referring_file=target,
                raw_input="",
                completion=self._complete_fallback,
            )
        )

    def _complete_fallback(
        self,
        key: tuple[Path, int, int],
        _referring_file: Path,
        _raw_input: str,
        image: QImage | None,
        error: str | None,
    ) -> None:
        target = key[0].resolve()
        emissions: list[tuple[str, str, QImage]] = []
        next_request: tuple[Path, str, tuple[Path, int, int]] | None = None

        with self._lock:
            if self._running_key_by_target.get(target) == key:
                self._running_key_by_target.pop(target, None)

            if error is not None or image is None or image.isNull():
                self._failed.add(key)
            elif self._is_newer_than_displayed(target, key):
                stored = QImage(image)
                self._displayed_key_by_target[target] = key
                self._latest_image_by_target[target] = stored
                self._cache = {
                    cache_key: cached
                    for cache_key, cached in self._cache.items()
                    if cache_key[0].resolve() != target
                }
                self._cache[key] = stored
                self._failed = {
                    failed_key
                    for failed_key in self._failed
                    if failed_key[0].resolve() != target
                }
                for referring, raw in self._watchers_by_target.get(target, set()):
                    emissions.append((referring, raw, QImage(stored)))

            latest_request = self._latest_request_by_target.get(target)
            if latest_request is not None:
                source, latest_key = latest_request
                if latest_key == key:
                    self._latest_request_by_target.pop(target, None)
                elif latest_key not in self._failed:
                    self._running_key_by_target[target] = latest_key
                    next_request = (target, source, latest_key)

        for referring, raw, stored in emissions:
            self.preview_ready.emit(referring, raw, stored)
        if next_request is not None:
            self._start_fallback_render(*next_request)

    def _is_newer_than_displayed(
        self,
        target: Path,
        key: tuple[Path, int, int],
    ) -> bool:
        displayed = self._displayed_key_by_target.get(target)
        if displayed is None:
            return True
        return (key[1], key[2]) >= (displayed[1], displayed[2])
