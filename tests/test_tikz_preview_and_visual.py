"""Static regression checks for TikZ Preview path materialization and non-blocking Visual projection."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_preview_builder_materializes_workspace_rooted_references() -> None:
    builder = _read(
        "src/nd_mind_mirror/core/render/latex/latex_preview_source_builder.py"
    )
    renderer = _read(
        "src/nd_mind_mirror/core/render/latex/latex_renderer.py"
    )
    window = _read(
        "src/nd_mind_mirror/ui/window/main/enhanced_main_window.py"
    )
    assert "LatexPreviewReferenceMaterializer" in builder
    assert "set_workspace_default_path" in builder
    assert "_preview_source_builder.set_workspace_default_path" in renderer
    assert "self._renderer.set_workspace_default_path" in window


def test_visual_tikz_render_is_not_run_on_gui_thread() -> None:
    visual = _read(
        "src/nd_mind_mirror/ui/editor/latex/windowed_latex_visual_editor.py"
    )
    service = _read(
        "src/nd_mind_mirror/ui/editor/latex/tikz_visual_preview_service.py"
    )
    task = _read(
        "src/nd_mind_mirror/ui/editor/latex/tikz_visual_preview_render_task.py"
    )
    assert "preview_for_input" in visual
    assert "preview_ready.connect" in visual
    assert "QThreadPool.globalInstance()" in service
    assert "TikZVisualPreviewRenderTask" in service
    assert "class TikZVisualPreviewRenderTask(QRunnable)" in task
    assert "self._renderer.render" not in visual


def test_visual_tikz_failures_are_revision_cached() -> None:
    service = _read(
        "src/nd_mind_mirror/ui/editor/latex/tikz_visual_preview_service.py"
    )
    assert "self._pending" in service
    assert "self._failed" in service
    assert "key in self._pending or key in self._failed" in service


def test_tikz_renderer_does_not_recursively_search_whole_workspace() -> None:
    renderer = _read(
        "src/nd_mind_mirror/graphic/tikz/bridge/renderer.py"
    )
    assert "LatexPreviewReferenceMaterializer" in renderer
    assert 'texinputs = [str(source_file.parent)]' in renderer
    assert 'f"{self.workspace}//"' not in renderer
    assert "except subprocess.TimeoutExpired" in renderer
