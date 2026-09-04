from pathlib import Path


def _enhanced_main_window_source() -> str:
    project_root = Path(__file__).resolve().parents[1]
    path = (
        project_root
        / "src"
        / "nd_mind_mirror"
        / "ui"
        / "window"
        / "main"
        / "enhanced_main_window.py"
    )
    return path.read_text(encoding="utf-8")


def test_session_string_lists_are_sanitized_before_restore() -> None:
    source = _enhanced_main_window_source()
    restore_method = source.split("def _restore_session", 1)[1].split(
        "def _save_session", 1
    )[0]

    assert "_sanitize_session_string_lists()" in restore_method
    assert "super()._restore_session()" in restore_method
    assert restore_method.index("_sanitize_session_string_lists()") < restore_method.index(
        "super()._restore_session()"
    )


def test_session_string_lists_are_sanitized_after_save() -> None:
    source = _enhanced_main_window_source()
    save_method = source.split("def _save_session", 1)[1].split(
        "def _sanitize_session_string_lists", 1
    )[0]

    assert "super()._save_session()" in save_method
    assert "_sanitize_session_string_lists()" in save_method
    assert save_method.index("super()._save_session()") < save_method.index(
        "_sanitize_session_string_lists()"
    )
