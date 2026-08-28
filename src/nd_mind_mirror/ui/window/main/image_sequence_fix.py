"""Keep image numbering monotonic, image sizing faithful, and stale PDF metadata cleared."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QTextCursor

from nd_mind_mirror.core.clipboard.image.clipboard_image_saver import ClipboardImageSaver
from nd_mind_mirror.core.latex.input.recursive.recursive_input_resolver import (
    RecursiveInputResolver,
)
from nd_mind_mirror.graphic.core.document_manager import GraphicDocumentManager
from nd_mind_mirror.ui.editor.latex.latex_visual_editor import LatexVisualEditor
from nd_mind_mirror.ui.preview.latex.latex_preview import LatexPreview


class ImageSequenceFix:
    """Apply monotonic image names, faithful Visual image widths, and source-local preview paths."""

    _installed = False
    _PATTERN = re.compile(r"^img_(\d+)\.png$", re.IGNORECASE)
    _INCLUDE_OPTIONS = re.compile(r"\\includegraphics\s*\[(?P<options>[^\]]*)\]", re.IGNORECASE)
    _INCLUDEGRAPHICS = re.compile(
        r"(?P<prefix>\\includegraphics\s*(?:\[[^\]]*\]\s*)?)"
        r"\{(?P<path>[^{}]+)\}",
        re.IGNORECASE,
    )
    _GRAPHIC_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".svg", ".eps", ".webp")
    _RELATIVE_WIDTH = re.compile(
        r"(?:^|,)\s*width\s*=\s*(?P<ratio>[0-9]*\.?[0-9]+)\s*"
        r"\\(?:textwidth|linewidth|columnwidth)\s*(?:,|$)",
        re.IGNORECASE,
    )
    _RESIZE_DEBOUNCE_MS = 90

    @classmethod
    def install(cls) -> None:
        """Install the shared image allocator, Visual sizing, source-local preview paths, and reset guards."""
        if cls._installed:
            return

        def save(image_saver, mime_data, tex_path):
            image = image_saver._extract_image(mime_data)
            if image is None or image.isNull():
                return None
            source_path = Path(tex_path).expanduser().resolve()
            target_path = cls.next_png(source_path.parent)
            if not image.save(str(target_path), "PNG"):
                return None
            return target_path

        def next_available_path(directory, *, base_name="img", extension=".jpg"):
            directory_path = Path(directory)
            suffix = extension if str(extension).startswith(".") else f".{extension}"
            pattern = re.compile(
                rf"^{re.escape(str(base_name))}_(\d+){re.escape(suffix)}$",
                re.IGNORECASE,
            )
            highest = -1
            try:
                for candidate in directory_path.iterdir():
                    match = pattern.match(candidate.name)
                    if match is not None:
                        highest = max(highest, int(match.group(1)))
            except OSError:
                pass
            return directory_path / f"{base_name}_{highest + 1}{suffix}"

        def next_graphic_path(manager, directory):
            del manager
            return cls.next_png(Path(directory))

        ClipboardImageSaver.save = save
        ClipboardImageSaver.next_available_path = staticmethod(next_available_path)
        GraphicDocumentManager._next_image_path = next_graphic_path
        cls._patch_preview_graphic_paths()
        cls._patch_visual_image_size()
        cls._patch_preview_source_reset()
        cls._installed = True

    @classmethod
    def next_png(cls, directory: Path) -> Path:
        """Return max(existing img_N PNG/sidecar index)+1 in one source folder."""
        directory = Path(directory)
        highest = -1
        try:
            for candidate in directory.iterdir():
                name = candidate.name
                if candidate.suffix.lower() == ".ndgraphic":
                    name = candidate.with_suffix(".png").name
                match = cls._PATTERN.match(name)
                if match is not None:
                    highest = max(highest, int(match.group(1)))
        except OSError:
            pass
        return directory / f"img_{highest + 1}.png"

    @classmethod
    def _width_ratio(cls, raw: str) -> float | None:
        """Extract width=N\\textwidth/linewidth/columnwidth from one graphic block."""
        include = cls._INCLUDE_OPTIONS.search(str(raw))
        if include is None:
            return None
        match = cls._RELATIVE_WIDTH.search(include.group("options"))
        if match is None:
            return None
        try:
            return max(0.05, min(float(match.group("ratio")), 2.0))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _visual_text_width(editor: LatexVisualEditor) -> float:
        """Return the actual visible text area instead of the old arbitrary -70 px estimate."""
        viewport = editor.viewport()
        width = float(viewport.contentsRect().width())
        document = editor.document()
        frame = document.rootFrame()
        if frame is not None:
            fmt = frame.frameFormat()
            width -= float(fmt.leftMargin() + fmt.rightMargin())
        return max(width - 8.0, 120.0)

    @classmethod
    def _resize_block_image(cls, editor: LatexVisualEditor, block, raw: str) -> None:
        """Resize image objects in one Visual block to the explicit LaTeX relative width."""
        ratio = cls._width_ratio(raw)
        if ratio is None or not block.isValid():
            return
        target_width = max(cls._visual_text_width(editor) * ratio, 1.0)
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.isValid():
                char_format = fragment.charFormat()
                if char_format.isImageFormat():
                    image_format = char_format.toImageFormat()
                    old_width = max(float(image_format.width()), 1.0)
                    old_height = max(float(image_format.height()), 1.0)
                    target_height = old_height * target_width / old_width
                    image_format.setWidth(target_width)
                    image_format.setHeight(max(target_height, 1.0))
                    selection = QTextCursor(editor.document())
                    selection.setPosition(fragment.position())
                    selection.setPosition(
                        fragment.position() + fragment.length(),
                        QTextCursor.MoveMode.KeepAnchor,
                    )
                    selection.setCharFormat(image_format)
            iterator += 1

    @classmethod
    def _resize_all_graphics(cls, editor: LatexVisualEditor) -> None:
        """Reapply source-defined relative widths after viewport/resource/layout changes."""
        was_loading = editor._loading
        editor._loading = True
        editor._emit_timer.stop()
        try:
            block = editor.document().firstBlock()
            while block.isValid():
                data = block.userData()
                raw = str(getattr(data, "raw", "")) if data is not None else ""
                if raw and "\\includegraphics" in raw:
                    cls._resize_block_image(editor, block, raw)
                block = block.next()
        finally:
            editor._loading = was_loading
        editor.viewport().update()

    @classmethod
    def _schedule_visual_resize(cls, editor: LatexVisualEditor) -> None:
        """Coalesce repeated layout/resource events into one full-document image pass."""
        timer = getattr(editor, "_nd_image_resize_timer", None)
        if timer is None:
            timer = QTimer(editor)
            timer.setSingleShot(True)
            timer.setInterval(cls._RESIZE_DEBOUNCE_MS)
            timer.timeout.connect(lambda e=editor: cls._resize_all_graphics(e))
            editor._nd_image_resize_timer = timer
        timer.start()

    @classmethod
    def _patch_visual_image_size(cls) -> None:
        """Make Visual image width track explicit LaTeX width without repeated whole-document scans."""
        original_insert = LatexVisualEditor._insert_graphic_block
        original_refresh = LatexVisualEditor.refresh_graphic_resources
        original_resize_event = LatexVisualEditor.resizeEvent
        original_load_source = LatexVisualEditor.load_source

        def insert_graphic_block(editor, cursor, raw, graphic_path, source_line=0):
            original_insert(editor, cursor, raw, graphic_path, source_line=source_line)
            # The newly inserted block is cheap to size immediately. Any other
            # affected graphics are handled once by the coalesced pass.
            cls._resize_block_image(editor, cursor.block(), raw)
            cls._schedule_visual_resize(editor)

        def refresh_graphic_resources(editor):
            result = original_refresh(editor)
            cls._schedule_visual_resize(editor)
            return result

        def resize_event(editor, event):
            original_resize_event(editor, event)
            cls._schedule_visual_resize(editor)

        def load_source(editor, source, source_path=None):
            result = original_load_source(editor, source, source_path)
            cls._schedule_visual_resize(editor)
            return result

        LatexVisualEditor._insert_graphic_block = insert_graphic_block
        LatexVisualEditor.refresh_graphic_resources = refresh_graphic_resources
        LatexVisualEditor.resizeEvent = resize_event
        LatexVisualEditor.load_source = load_source

    @classmethod
    def _patch_preview_graphic_paths(cls) -> None:
        """Resolve each relative includegraphics path beside the file that owns that source line."""
        original_resolve_line_code = RecursiveInputResolver._resolve_line_code

        def resolve_line_code(
            resolver,
            code,
            containing_file,
            stack,
            context,
            current_heading,
            heading_mapping,
        ):
            rewritten = cls._rewrite_includegraphics_paths(
                str(code),
                Path(containing_file),
            )
            return original_resolve_line_code(
                resolver,
                rewritten,
                containing_file,
                stack,
                context,
                current_heading,
                heading_mapping,
            )

        RecursiveInputResolver._resolve_line_code = resolve_line_code

    @classmethod
    def _rewrite_includegraphics_paths(cls, code: str, containing_file: Path) -> str:
        """Make existing relative graphic files absolute without touching macro-based references."""
        parent = Path(containing_file).expanduser().resolve().parent

        def replace(match: re.Match[str]) -> str:
            raw = match.group("path").strip()
            if not raw or raw.startswith("\\") or "://" in raw:
                return match.group(0)

            candidate = Path(raw).expanduser()
            if candidate.is_absolute():
                return match.group(0)

            base = parent / candidate
            options = [base]
            if not candidate.suffix:
                options = [base.with_suffix(extension) for extension in cls._GRAPHIC_EXTENSIONS]

            resolved: Path | None = None
            for option in options:
                try:
                    current = option.resolve()
                except OSError:
                    continue
                if current.is_file():
                    resolved = current
                    break

            if resolved is None:
                return match.group(0)

            return f"{match.group('prefix')}{{{resolved.as_posix()}}}"

        return cls._INCLUDEGRAPHICS.sub(replace, str(code))

    @staticmethod
    def _patch_preview_source_reset() -> None:
        """Prevent the old PDF's page count from reappearing while a new source renders."""
        previous_set_source_document = LatexPreview.set_source_document

        def set_source_document(preview, path) -> None:
            source_path = Path(path).expanduser().resolve()
            changed = source_path != preview._source_document_path
            previous_set_source_document(preview, source_path)
            if not changed:
                return
            pdf_view = preview._pdf_view
            try:
                pdf_view._fit_document.close()
            except Exception:
                pass
            pdf_view._fit_document_path = None
            pdf_view._rendered_bounds_cache.clear()
            pdf_view._last_view_status = None
            try:
                zoom = float(pdf_view.view_status()[0])
            except Exception:
                zoom = 100.0
            preview.view_status_changed.emit(zoom, 0, 0)

        LatexPreview.set_source_document = set_source_document
