from pathlib import Path


def test_visual_typography_is_guarded_from_source_serialization():
    source = Path(
        'src/nd_mind_mirror/ui/editor/latex/latex_visual_editor.py'
    ).read_text(encoding='utf-8')

    assert 'self._has_loaded_source = False' in source
    assert 'if self._loading or not self._has_loaded_source:' in source
    assert 'self._emit_timer.stop()' in source
    assert 'self._has_loaded_source = True' in source
