"""Background rendering worker for cancellable Source-mode LaTeX previews."""

from __future__ import annotations

from threading import Event

from PySide6.QtCore import QObject, Signal, Slot

from nd_mind_mirror.ui.editor.latex.source_latex_preview_renderer import (
    SourceLatexPreviewRenderer,
    SourcePreviewRenderCancelled,
)


class SourceLatexPreviewRenderWorker(QObject):
    """Render one coalesced snippet batch outside the GUI thread and support mode cancellation."""

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
        self._cancel_event = Event()

    def cancel(self) -> None:
        """Request cooperative cancellation from the GUI thread."""
        self._cancel_event.set()

    @Slot()
    def render(self) -> None:
        """Render the requested batch and always release the worker thread."""
        images: dict[str, object] = {}
        attempted: tuple[str, ...] = tuple(self._snippets)
        try:
            renderer = SourceLatexPreviewRenderer(cancel_event=self._cancel_event)
            images = renderer.render_many(self._snippets)
        except SourcePreviewRenderCancelled:
            images = {}
            attempted = ()
        except Exception:
            # Preview rendering is optional presentation work. A renderer error
            # must never terminate the GUI thread or strand the worker thread.
            images = {}
        finally:
            self.completed.emit(
                self._generation,
                images,
                attempted,
            )
            self.finished.emit()
