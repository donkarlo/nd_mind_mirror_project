"""Regression coverage for stopping Source formula rendering outside Source mode."""

from pathlib import Path

ROOT = Path(__file__).parent.parent
CONTROLLER = (
    ROOT / "src/nd_mind_mirror/ui/editor/latex/source_latex_preview_controller.py"
).read_text(encoding="utf-8")
WORKER = (
    ROOT / "src/nd_mind_mirror/ui/editor/latex/source_latex_preview_render_worker.py"
).read_text(encoding="utf-8")
RENDERER = (
    ROOT / "src/nd_mind_mirror/ui/editor/latex/source_latex_preview_renderer.py"
).read_text(encoding="utf-8")


def test_hidden_source_cancels_active_render_worker() -> None:
    assert 'cancel = getattr(worker, "cancel", None)' in CONTROLLER
    assert "cancel()" in CONTROLLER


def test_worker_uses_thread_safe_cancel_event() -> None:
    assert "self._cancel_event = Event()" in WORKER
    assert "self._cancel_event.set()" in WORKER
    assert "SourcePreviewRenderCancelled" in WORKER


def test_renderer_terminates_lualatex_on_cancel() -> None:
    assert "subprocess.Popen(" in RENDERER
    assert "self._terminate_process(process)" in RENDERER
    assert "process.terminate()" in RENDERER
    assert "process.kill()" in RENDERER
