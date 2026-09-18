from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _method_source(relative: str, class_name: str, method_name: str) -> str:
    source = _source(relative)
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == method_name:
                    segment = ast.get_source_segment(source, child)
                    assert segment is not None
                    return segment
    raise AssertionError(f"Missing {class_name}.{method_name}")


def test_tikz_open_is_source_only_and_explicit_render_is_idle_coalesced() -> None:
    relative = "src/nd_mind_mirror/graphic/bridge/configured_unified_server.py"
    open_source = _method_source(
        relative,
        "ConfiguredUnifiedGraphicBridgeServer",
        "_send_tikz_open",
    )
    render_source = _method_source(
        relative,
        "ConfiguredUnifiedGraphicBridgeServer",
        "_send_tikz_render",
    )
    assert "_schedule_tikz_render" not in open_source
    assert "_render_pending_tikz_after_idle" in render_source
    assert ".cancel()" in render_source


def test_live_preview_path_cannot_start_lualatex_fallback() -> None:
    relative = "src/nd_mind_mirror/ui/editor/latex/tikz_preview/render_coordinator.py"
    request_source = _method_source(
        relative,
        "TikZPreviewRenderCoordinator",
        "request",
    )
    live_guard = request_source.index("if not allow_fallback:")
    fallback_start = request_source.index("self._start_fallback_render")
    assert live_guard < fallback_start


def test_desktop_live_refresh_is_bounded_and_idle_fallback_is_separate() -> None:
    source = _source(
        "src/nd_mind_mirror/ui/window/main/enhanced_main_window.py"
    )
    assert "_TIKZ_LIVE_INTERVAL_MS = 180" in source
    assert "_TIKZ_FALLBACK_IDLE_MS = 1200" in source
    assert "allow_fallback=False" in source
    assert "allow_fallback=True" in source
    assert "_tikz_pdf_compile_timer.stop()" in source


def test_bridge_version_marks_idle_render_policy() -> None:
    source = _source("src/nd_mind_mirror/graphic/bridge/__init__.py")
    assert '__version__ = "0.31.51"' in source
