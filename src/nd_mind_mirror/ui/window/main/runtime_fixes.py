"""Install focused runtime fixes for preview, images, bookmarks, fractions, and Structure UI."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QTimer

from nd_mind_mirror.core.clipboard.image.clipboard_image_saver import ClipboardImageSaver
from nd_mind_mirror.core.latex.direction.latex_text_direction_resolver import (
    DirectionDecision,
    LatexTextDirectionResolver,
    TextDirection,
)
from nd_mind_mirror.graphic.core.document_manager import GraphicDocumentManager
from nd_mind_mirror.ui.editor.latex.latex_visual_editor import LatexVisualEditor
from nd_mind_mirror.ui.preview.latex.latex_preview import LatexPreview
from nd_mind_mirror.ui.preview.pdf.selectable_pdf_view import SelectablePdfView
from nd_mind_mirror.ui.window.main.preview_auto_fit_controller import PreviewAutoFitController


class LateRuntimeFixes:
    """Install the focused fixes exactly once before the main window is created."""

    _installed = False

    @classmethod
    def install(cls) -> None:
        """Patch stable classes without rewriting their large implementations."""
        if cls._installed:
            return
        cls._patch_image_naming()
        cls._patch_fraction_projection()
        cls._patch_preview_page_status()
        cls._patch_auto_fit()
        cls._installed = True

    @staticmethod
    def _next_img_path(directory: Path) -> Path:
        """Allocate the first free img_N.png shared by clipboard and iPad graphics."""
        counter = 0
        while True:
            candidate = directory / f"img_{counter}.png"
            if not candidate.exists() and not candidate.with_suffix(".ndgraphic").exists():
                return candidate
            counter += 1

    @classmethod
    def _patch_image_naming(cls) -> None:
        """Use collision-safe img_N.png names for both clipboard and iPad inserts."""
        def save(image_saver, mime_data, tex_path):
            image = image_saver._extract_image(mime_data)
            if image is None or image.isNull():
                return None
            source_path = Path(tex_path).expanduser().resolve()
            target_path = cls._next_img_path(source_path.parent)
            if not image.save(str(target_path), "PNG"):
                return None
            return target_path

        def next_available_path(directory, *, base_name="img", extension=".jpg"):
            directory_path = Path(directory)
            suffix = extension if str(extension).startswith(".") else f".{extension}"
            counter = 0
            while True:
                candidate = directory_path / f"{base_name}_{counter}{suffix}"
                if not candidate.exists():
                    return candidate
                counter += 1

        def next_graphic_path(manager, directory):
            del manager
            return cls._next_img_path(Path(directory))

        ClipboardImageSaver.save = save
        ClipboardImageSaver.next_available_path = staticmethod(next_available_path)
        GraphicDocumentManager._next_image_path = next_graphic_path

    @staticmethod
    def _fraction_text(raw_text: str) -> str | None:
        """Render a simple or nested LaTeX fraction as readable Unicode slash notation."""
        text = str(raw_text).strip()
        if text.startswith("$") and text.endswith("$") and len(text) >= 2:
            text = text[1:-1].strip()
        elif text.startswith(r"\(") and text.endswith(r"\)"):
            text = text[2:-2].strip()

        def read_group(value: str, start: int) -> tuple[str, int] | None:
            if start >= len(value) or value[start] != "{":
                return None
            depth = 0
            escaped = False
            for index in range(start, len(value)):
                char = value[index]
                if escaped:
                    escaped = False
                    continue
                if char == "\\":
                    escaped = True
                    continue
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        return value[start + 1:index], index + 1
            return None

        def convert(value: str) -> str:
            value = value.strip()
            if not value.startswith(r"\frac"):
                return value
            first = read_group(value, len(r"\frac"))
            if first is None:
                return value
            numerator, after_first = first
            second = read_group(value, after_first)
            if second is None:
                return value
            denominator, after_second = second
            if value[after_second:].strip():
                return value
            numerator_display = convert(numerator)
            denominator_display = convert(denominator)
            if len(numerator_display) > 1 and "⁄" not in numerator_display:
                numerator_display = f"({numerator_display})"
            if len(denominator_display) > 1 and "⁄" not in denominator_display:
                denominator_display = f"({denominator_display})"
            return f"{numerator_display}⁄{denominator_display}"

        converted = convert(text)
        return converted if converted != text and "⁄" in converted else None

    @classmethod
    def _patch_fraction_projection(cls) -> None:
        """Keep raw fraction source intact while making Visual and math-heavy Source lines readable."""
        original_visual = LatexVisualEditor._visual_raw_inline_text
        original_decide = LatexTextDirectionResolver.decide

        def visual_raw_inline_text(_visual_cls, raw_text: str) -> str:
            fraction = cls._fraction_text(raw_text)
            return fraction if fraction is not None else original_visual(raw_text)

        def decide(resolver, line: str) -> DirectionDecision:
            stripped = str(line).strip()
            if r"\frac" in stripped and re.search(
                r"[\u0600-\u06ff\u0750-\u077f\u0870-\u089f\u08a0-\u08ff\ufb50-\ufdff\ufe70-\ufeff]",
                stripped,
            ) is None:
                return DirectionDecision(TextDirection.LEFT_TO_RIGHT, "fraction-math-line")
            return original_decide(resolver, line)

        LatexVisualEditor._visual_raw_inline_text = classmethod(visual_raw_inline_text)
        LatexTextDirectionResolver.decide = decide

    @staticmethod
    def _patch_preview_page_status() -> None:
        """Reset stale page labels on file switches and report the current PDF's real page count."""
        original_set_source_document = LatexPreview.set_source_document
        original_view_status = SelectablePdfView.view_status

        def set_source_document(preview, path):
            source_path = Path(path).expanduser().resolve()
            changed = source_path != preview._source_document_path
            zoom = preview._pdf_view.view_status()[0]
            original_set_source_document(preview, source_path)
            if changed:
                preview._message.setText(f"Rendering {source_path.name}…")
                preview._stack.setCurrentWidget(preview._message)
                preview._pdf_view._last_view_status = None
                preview.view_status_changed.emit(float(zoom), 0, 0)

        def view_status(pdf_view):
            zoom, page_number, _qml_count = original_view_status(pdf_view)
            try:
                page_count = int(pdf_view._fit_document.pageCount())
            except Exception:
                page_count = 0
            if page_count <= 0 or pdf_view._fit_document_path is None:
                return zoom, 0, 0
            return zoom, max(1, min(int(page_number or 1), page_count)), page_count

        LatexPreview.set_source_document = set_source_document
        SelectablePdfView.view_status = view_status

    @staticmethod
    def _patch_auto_fit() -> None:
        """Make Auto Fit use complete physical page width and the stable outer preview width."""
        def apply_fit(controller) -> None:
            if not controller._auto_enabled:
                return
            try:
                root = controller._pdf_view.rootObject()
                if root is None:
                    return
                document = controller._pdf_view._fit_document
                page_count = int(document.pageCount())
                if page_count <= 0:
                    return
                try:
                    page_index = max(int(root.property("currentPageIndex")), 0)
                except (TypeError, ValueError):
                    page_index = 0
                page_index = min(page_index, page_count - 1)
                page_width = max(float(document.pagePointSize(page_index).width()), 1.0)
                try:
                    viewport_width = float(root.property("width"))
                except (TypeError, ValueError):
                    viewport_width = float(controller._pdf_view.width())
                if viewport_width <= 1.0:
                    viewport_width = float(controller._pdf_view.width())
                try:
                    ratio = float(root.property("fitWidthRatio"))
                except (TypeError, ValueError):
                    ratio = 0.95
                ratio = max(0.50, min(ratio, 1.0))
                scale = max(
                    controller._pdf_view._MIN_ZOOM,
                    min((viewport_width * ratio) / page_width, controller._pdf_view._MAX_ZOOM),
                )
                root.setProperty("fitPageWidthPoints", page_width)
                root.setProperty("fitContentWidthPoints", 0.0)
                root.setProperty("fitContentCenterRatioX", 0.5)
                root.setProperty("zoomScale", float(scale))
                scheduler = getattr(controller, "_schedule_recenter", None)
                if callable(scheduler):
                    scheduler()
                else:
                    QTimer.singleShot(120, lambda: root.centerHorizontally())
            except Exception:
                return

        PreviewAutoFitController._apply_fit = apply_fit
