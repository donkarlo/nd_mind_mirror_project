"""Background rendering worker for Source-mode LaTeX previews."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from nd_mind_mirror.ui.editor.latex.source_latex_preview_renderer import (
    SourceLatexPreviewRenderer,
)


class SourceLatexPreviewRenderWorker(QObject):
    """Render one coalesced snippet batch outside the GUI thread."""

    completed = Signal(int, object, object)
    finished = Signal()

    def __init__(
        self,
        generation: int,
        snippets: list[str],
    ) -> None:
        super().__init__()
        self._generation = int(generation)
        self._snippets = [str(item) for item in snippets if str(item).strip()]

    @Slot()
    def render(self) -> None:
        """Render the requested batch and always release the worker thread."""
        images: dict[str, object] = {}
        try:
            renderer = SourceLatexPreviewRenderer()
            images = renderer.render_many(self._snippets)
        except Exception:
            # Preview rendering is optional presentation work. A renderer error
            # must never terminate the GUI thread or strand the worker thread.
            images = {}
        finally:
            self.completed.emit(
                self._generation,
                images,
                tuple(self._snippets),
            )
            self.finished.emit()
