from pathlib import Path


def test_fit_source_sync_recenters_and_edit_phrase_uses_native_pdf_search():
    qml = Path(
        "src/nd_mind_mirror/ui/preview/pdf/selectable_pdf_view.qml"
    ).read_text(encoding="utf-8")
    preview = Path(
        "src/nd_mind_mirror/ui/preview/latex/latex_preview.py"
    ).read_text(encoding="utf-8")

    assert "property bool syncRecenterHorizontal" in qml
    assert "syncHorizontalCenter.restart()" in qml
    assert "searchString: root.editHighlightText" in qml
    assert "keep_horizontal_center=self._fit_active" in preview
