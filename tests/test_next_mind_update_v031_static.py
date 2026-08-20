from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_live_preview_fit_is_not_recomputed_on_every_render():
    text = (ROOT / "src/nd_mind_mirror/ui/preview/latex/latex_preview.py").read_text()
    assert "_fit_pending_for_source" in text
    assert "Compute the expensive content-aware Fit only for the first PDF" in text


def test_synctex_waits_for_matching_pdf_generation():
    text = (ROOT / "src/nd_mind_mirror/core/render/latex/latex_renderer.py").read_text()
    assert "_last_published_generation" in text
    assert "_preview_is_current_for_sync" in text
    assert "stale SyncTeX/PDF" in text


def test_navigator_new_latex_uses_configured_template():
    text = (ROOT / "src/nd_mind_mirror/ui/panel/file_system/file_system_panel.py").read_text()
    assert "_choose_latex_template" in text
    assert '"LaTeX template:"' in text
    assert "template_content if latex else" in text
