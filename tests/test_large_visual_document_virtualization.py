from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from nd_mind_mirror.core.latex.visual.visual_source_window import (
    VisualSourceWindow,
)
from nd_mind_mirror.core.settings.visual.visual_window_settings import (
    VisualWindowSettings,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _settings() -> VisualWindowSettings:
    return VisualWindowSettings(
        large_document_threshold_chars=120_000,
        pages_above=2,
        pages_below=2,
        estimated_chars_per_page=2400,
        min_lines_per_page=12,
        max_lines_per_page=45,
        rewindow_delay_ms=90,
        scroll_edge_ratio=0.14,
    )


def _large_story(line_count: int = 28_000) -> str:
    lines = [
        r"\documentclass{article}",
        r"\begin{document}",
    ]
    for index in range(1, line_count + 1):
        if index % 2000 == 0:
            lines.append(rf"\section{{Section {index}}}")
        lines.append(
            f"{index} این یک خط نسبتاً بلند از متن داستان برای آزمون سند بزرگ است. "
            "این جمله عمداً تکرار می‌شود تا حجم فایل واقعی شبیه‌سازی شود."
        )
    lines.append(r"\end{document}")
    return "\n".join(lines) + "\n"


def test_large_visual_projection_is_bounded_around_focus() -> None:
    source = _large_story()
    focus_line = 14_000
    settings = _settings()

    model = VisualSourceWindow(source, settings, focus_line=focus_line)

    assert len(source) > 3_000_000
    assert model.virtualized is True
    assert model.contains_line(focus_line)
    assert model.window_char_count <= settings.hard_window_chars
    assert model.window_char_count < len(source) // 20


def test_visual_window_edit_preserves_complete_source_outside_window() -> None:
    source = _large_story(8_000)
    model = VisualSourceWindow(source, _settings(), focus_line=4_000)
    before = source[:model.window_start]
    after = source[model.window_end:]
    replacement = model.window_source.replace("داستان", "رمان", 1)

    updated = model.splice(replacement)

    assert updated.startswith(before)
    assert updated.endswith(after)
    assert "Section 2000" in updated
    assert "Section 6000" in updated
    assert len(updated) > len(model.window_source) * 10


def test_visual_window_settings_read_user_page_count_and_legacy_typo(tmp_path) -> None:
    settings_path = tmp_path / "settings.yaml"
    settings_path.write_text(
        "editor:\n"
        "  visual_window_pages_above: 2\n"
        "  visual_window_pages_below: 2\n"
        "  visual_window_estimated_chars_per_page: 2400\n"
        "  visual_window_min_lines_per_peage: 13\n"
        "  visual_window_max_lines_per_page: 44\n"
        "  visual_window_rewindow_delay_ms: 95\n"
        "  visual_window_scroll_edge_ratio: 0.15\n",
        encoding="utf-8",
    )
    app_settings = SimpleNamespace(
        settings_path=settings_path,
        editor_visual_large_document_threshold_chars=120_000,
    )

    settings = VisualWindowSettings.from_app_settings(app_settings)

    assert settings.pages_above == 2
    assert settings.pages_below == 2
    assert settings.min_lines_per_page == 13
    assert settings.hard_window_chars <= 96_000


def test_visual_controller_has_no_runtime_method_replacement() -> None:
    source = (
        PROJECT_ROOT
        / "src/nd_mind_mirror/ui/window/main/visual_window_controller.py"
    ).read_text(encoding="utf-8")

    assert "MethodType" not in source
    assert "visual.load_source =" not in source
    assert "visual.serialized_source =" not in source
    assert "visual.go_to_source_location =" not in source
    assert "visual.set_selection_from_source_locations =" not in source
    assert "source_changed.disconnect(editor._apply_visual_source)" in source


def test_structure_continues_to_parse_complete_canonical_source() -> None:
    main_window = (
        PROJECT_ROOT
        / "src/nd_mind_mirror/ui/window/main/main_window.py"
    ).read_text(encoding="utf-8")
    structure_panel = (
        PROJECT_ROOT
        / "src/nd_mind_mirror/ui/panel/structure/latex_structure_panel.py"
    ).read_text(encoding="utf-8")
    visual_controller = (
        PROJECT_ROOT
        / "src/nd_mind_mirror/ui/window/main/visual_window_controller.py"
    ).read_text(encoding="utf-8")

    assert "self._structure_panel.set_document(\n            path,\n            content," in main_window
    assert "self._source = source" in structure_panel
    assert "self._latex_parser.parse(self._source)" in structure_panel
    assert "structure_panel.set_document" not in visual_controller
