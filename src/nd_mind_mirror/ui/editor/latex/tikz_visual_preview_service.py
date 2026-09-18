"""Shared asynchronous TikZ previews for LaTeX Source and Visual modes."""

from __future__ import annotations

from pathlib import Path
import re

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage

from nd_mind_mirror.core.workspace.path.workspace_reference_resolver import (
    WorkspaceReferenceResolver,
)
from nd_mind_mirror.ui.editor.latex.tikz_preview.render_coordinator import (
    TikZPreviewRenderCoordinator,
)


class TikZVisualPreviewService(QObject):
    """Resolve TikZ inputs and reuse one serialized renderer/cache per workspace."""

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
        self._coordinator = TikZPreviewRenderCoordinator.shared(
            self._workspace_root
        )
        self._requested_contexts: set[tuple[str, str]] = set()
        self._coordinator.preview_ready.connect(
            self._on_shared_preview_ready
        )

    def target_for_input(
        self,
        raw: str,
        referring_file: str | Path | None,
    ) -> Path | None:
        """Resolve a raw input/include to its canonical target without rendering it."""
        if referring_file in (None, ""):
            return None
        match = self._INPUT.match(str(raw).strip())
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
        return target.expanduser().resolve()

    def preview_for_input(
        self,
        raw: str,
        referring_file: str | Path | None,
        *,
        allow_fallback: bool = True,
    ) -> QImage | None:
        """Return a preview while optionally forbidding expensive LuaLaTeX fallback."""
        request = self._resolve_request(raw, referring_file)
        if request is None:
            return None
        target, source, key, referring_path = request
        context = (str(referring_path), raw)
        self._requested_contexts.add(context)
        return self._coordinator.request(
            target=target,
            source=source,
            key=key,
            referring_file=referring_path,
            raw_input=raw,
            allow_fallback=bool(allow_fallback),
        )

    def _resolve_request(
        self,
        raw: str,
        referring_file: str | Path | None,
    ) -> tuple[Path, str, tuple[Path, int, int], Path] | None:
        target = self.target_for_input(raw, referring_file)
        if target is None or referring_file in (None, ""):
            return None
        referring_path = Path(referring_file).expanduser().resolve()
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

    def _on_shared_preview_ready(
        self,
        referring_file: str,
        raw_input: str,
        image: object,
    ) -> None:
        context = (referring_file, raw_input)
        if context not in self._requested_contexts:
            return
        if not isinstance(image, QImage) or image.isNull():
            return
        self.preview_ready.emit(
            referring_file,
            raw_input,
            QImage(image),
        )
