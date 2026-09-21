"""Regression checks for Navigator clipboard and local-image MIME handling."""

from pathlib import Path

from PySide6.QtCore import QMimeData, QUrl

from nd_mind_mirror.core.clipboard.image.clipboard_image_saver import (
    ClipboardImageSaver,
)


ROOT = Path(__file__).resolve().parents[1]

FILE_MIME = (
    ROOT
    / "src/nd_mind_mirror/core/clipboard/file_clipboard_mime_data_controller.py"
).read_text(encoding="utf-8")
SEARCH_AWARE = (
    ROOT
    / "src/nd_mind_mirror/ui/window/main/search_aware_navigator_multi_path_context_controller.py"
).read_text(encoding="utf-8")
IMAGE_SAVER = (
    ROOT
    / "src/nd_mind_mirror/core/clipboard/image/clipboard_image_saver.py"
).read_text(encoding="utf-8")
IMAGE_RESOLVER = (
    ROOT
    / "src/nd_mind_mirror/core/clipboard/image/image_mime_reference_resolver.py"
).read_text(encoding="utf-8")
MULTI_DROP = (
    ROOT
    / "src/nd_mind_mirror/ui/editor/latex/multi_image_drop_latex_editor.py"
).read_text(encoding="utf-8")
PUBLIC_LATEX = (
    ROOT
    / "src/nd_mind_mirror/ui/editor/latex/latex_editor.py"
).read_text(encoding="utf-8")


def test_navigator_file_copy_replaces_stale_system_clipboard_payload() -> None:
    assert "setUrls(" in FILE_MIME
    assert "application/x-nd-mind-mirror-file-clipboard" in FILE_MIME
    assert "publish_paths(paths)" in SEARCH_AWARE
    assert "dataChanged.connect" in SEARCH_AWARE
    assert "is_mind_mirror_file_payload" in SEARCH_AWARE


def test_external_local_file_urls_are_file_paste_sources() -> None:
    assert "FileClipboardMimeDataController.local_paths" in SEARCH_AWARE
    assert 'return self._top_level_paths(external), "copy"' in SEARCH_AWARE
    assert "sources, mode = self._clipboard_sources_and_mode()" in SEARCH_AWARE


def test_file_url_images_never_enter_navigator_pixel_image_paste_path() -> None:
    file_guard = IMAGE_SAVER.index(
        "FileClipboardMimeDataController.local_paths(mime_data)"
    )
    image_extract = IMAGE_SAVER.index(
        "image = self._extract_embedded_image(mime_data)",
        file_guard,
    )
    assert file_guard < image_extract


def test_plain_text_mime_is_not_consumed_as_an_image(tmp_path: Path) -> None:
    mime = QMimeData()
    mime.setText("plain source text")
    saver = ClipboardImageSaver()

    assert saver.save(mime, tmp_path / "source.tex") is None
    assert saver._extract_image(mime) is None


def test_single_local_image_is_kept_as_original_reference(tmp_path: Path) -> None:
    image = tmp_path / "original.png"
    image.write_bytes(b"reference-only")
    tex = tmp_path / "source.tex"
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(image))])

    reference = ClipboardImageSaver().save(mime, tex)

    assert reference == image.resolve()
    assert not (tmp_path / "source.png").exists()


def test_multi_image_drop_references_every_original_local_file() -> None:
    assert "def local_image_paths" in IMAGE_RESOLVER
    assert "def latex_reference_paths" in IMAGE_RESOLVER
    assert "for image_path in image_paths:" in IMAGE_RESOLVER
    assert "if not reference_paths:" in MULTI_DROP
    assert "for reference_path in reference_paths:" in MULTI_DROP
    assert "self._insert_figure(relative_path.as_posix())" in MULTI_DROP
    assert "MultiImageDropLatexEditor" in PUBLIC_LATEX


def test_navigator_context_menu_does_not_steal_text_clipboard_shortcuts() -> None:
    assert 'menu.addAction("Copy\\tCtrl+C")' in SEARCH_AWARE
    assert 'menu.addAction("Cut\\tCtrl+X")' in SEARCH_AWARE
    assert 'menu.addAction("Paste\\tCtrl+V")' in SEARCH_AWARE
    assert 'setShortcut(QKeySequence("Ctrl+C"))' not in SEARCH_AWARE
    assert 'setShortcut(QKeySequence("Ctrl+X"))' not in SEARCH_AWARE
    assert 'setShortcut(QKeySequence("Ctrl+V"))' not in SEARCH_AWARE
    assert "menu.deleteLater()" in SEARCH_AWARE
