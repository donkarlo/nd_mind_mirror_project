from pathlib import Path

from nd_mind_mirror.graphic.core.dependency_resolver import GraphicDependencyResolver
from nd_mind_mirror.graphic.core.document_manager import GraphicDocumentManager


def test_graphic_document_creation_and_collision_names(tmp_path: Path) -> None:
    source = tmp_path / "paper.tex"
    source.write_text("\\documentclass{article}\n", encoding="utf-8")
    manager = GraphicDocumentManager(directory_name="graphics", canvas_width=320, canvas_height=200)

    first = manager.create_for_source(source)
    second = manager.create_for_source(source)

    assert first.image_path.name == "graphic.png"
    assert second.image_path.name == "graphic_2.png"
    assert first.image_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert first.sidecar_path.suffix == ".ndgraphic"
    assert first.tex_reference == "graphic.png"


def test_graphic_reference_at_cursor_is_reopened_not_recreated(tmp_path: Path) -> None:
    source_path = tmp_path / "paper.tex"
    graphics = tmp_path / "graphics"
    graphics.mkdir()
    image = graphics / "graphic.png"
    image.write_bytes(b"png")
    source = "before\n\\includegraphics[width=0.95\\linewidth]{graphics/graphic.png}\nafter\n"
    manager = GraphicDocumentManager()
    position = source.index("includegraphics") + 5

    ref = manager.find_reference(source, source_path, position)

    assert ref is not None
    assert ref.image_path == image.resolve()
    assert ref.sidecar_path.exists()


def test_graphic_dependency_resolver_tracks_png(tmp_path: Path) -> None:
    source_path = tmp_path / "paper.tex"
    image = tmp_path / "graphics" / "graphic.png"
    image.parent.mkdir()
    image.write_bytes(b"png")
    source = r"\includegraphics[width=.9\linewidth]{graphics/graphic.png}"

    deps = GraphicDependencyResolver().collect(source, source_path)

    assert deps == [image.resolve()]


def test_desktop_and_ipad_sources_expose_graphic_workflow() -> None:
    root = Path("src/nd_mind_mirror")
    latex = (root / "ui/editor/latex/latex_editor.py").read_text(encoding="utf-8")
    visual = (root / "ui/editor/latex/latex_visual_editor.py").read_text(encoding="utf-8")
    html = (root / "graphic/web/index.html").read_text(encoding="utf-8")
    js = (root / "graphic/web/app.js").read_text(encoding="utf-8")

    assert "Insert image in iPad…" in latex
    assert "Edit image in iPad…" in latex
    assert "Insert image in iPad…" in visual
    assert "Edit image in iPad…" in visual
    assert 'type="color"' in html
    assert 'type="range"' in html
    assert "ev.pressure" in js
    assert "eraser" in js
    assert "scheduleSave" in js


def test_old_tikz_experiment_is_parked_outside_active_graphic_app() -> None:
    parked = Path("src/nd_mind_mirror/graphic/tikz_future/nd_tikz_sketch_v0_2_0")
    assert parked.exists()
    active = Path("src/nd_mind_mirror/graphic/web")
    active_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in active.iterdir()
        if path.suffix in {".html", ".js", ".css"}
    )
    assert "TikZSourceEditor" not in active_text
    assert "HandwritingRecognizer" not in active_text


def test_graphic_settings_are_configurable(tmp_path: Path) -> None:
    from nd_mind_mirror.core.settings.yaml.yaml_settings import YamlSettings

    settings_path = tmp_path / "settings.yaml"
    settings_path.write_text(
        "graphic:\n"
        "  directory: drawings\n"
        "  latex_width_ratio: 0.8\n"
        "  canvas_width: 1200\n"
        "  canvas_height: 700\n"
        "  bridge_http_url: http://127.0.0.1:9999\n"
        "  bridge_token: abc\n",
        encoding="utf-8",
    )
    settings = YamlSettings(settings_path)
    assert settings.graphic_directory_name == "drawings"
    assert settings.graphic_width_ratio == 0.8
    assert settings.graphic_canvas_width == 1200
    assert settings.graphic_canvas_height == 700
    assert settings.graphic_bridge_http_url.endswith(":9999")
    assert settings.graphic_bridge_token == "abc"


def test_default_graphic_is_created_beside_tex_source(tmp_path: Path) -> None:
    source = tmp_path / "chapter.tex"
    source.write_text("text\n", encoding="utf-8")
    manager = GraphicDocumentManager()

    document = manager.create_for_source(source)

    assert document.image_path.parent == tmp_path
    assert document.sidecar_path.parent == tmp_path
    assert document.tex_reference == "graphic.png"


def test_click_anywhere_in_figure_reopens_existing_ipad_image(tmp_path: Path) -> None:
    source_path = tmp_path / "chapter.tex"
    image = tmp_path / "graphic.png"
    image.write_bytes(b"png")
    source = (
        "before\n"
        "\\begin{figure}[H]\n"
        "    \\centering\n"
        "    \\includegraphics[width=0.9\\textwidth]{graphic.png}\n"
        "\\end{figure}\n"
        "after\n"
    )
    manager = GraphicDocumentManager()
    position = source.index("centering") + 2

    ref = manager.find_reference(source, source_path, position)

    assert ref is not None
    assert ref.image_path == image.resolve()


def test_visual_parser_has_figure_image_projection() -> None:
    visual = Path("src/nd_mind_mirror/ui/editor/latex/latex_visual_editor.py").read_text(encoding="utf-8")

    assert "figure_begin = re.match" in visual
    assert 'result.append((' in visual
    assert '"graphic",' in visual
    assert "raw_figure" in visual
    assert "graphic_inside.group(1).strip()" in visual


def test_source_insert_uses_requested_figure_template() -> None:
    latex = Path("src/nd_mind_mirror/ui/editor/latex/latex_editor.py").read_text(encoding="utf-8")
    assert 'f"{prefix}\\\\begin{{figure}}[H]\\n"' in latex
    assert 'f"{inner_indent}\\\\centering\\n"' in latex
    assert 'f"{inner_indent}\\\\includegraphics[width=0.9\\\\textwidth]"' in latex


def test_graphic_insert_and_update_are_sent_as_distinct_ipad_operations() -> None:
    latex = Path("src/nd_mind_mirror/ui/editor/latex/latex_editor.py").read_text(encoding="utf-8")
    notifier = Path("src/nd_mind_mirror/graphic/core/bridge_notifier.py").read_text(encoding="utf-8")
    bridge = Path("src/nd_mind_mirror/graphic/bridge/server.py").read_text(encoding="utf-8")

    assert 'operation="insert"' in latex
    assert 'operation="update"' in latex
    assert '"operation": operation' in notifier
    assert '"operation": self._normalize_operation' in bridge
