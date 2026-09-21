"""Compatibility installer for interaction features that do not own mode synchronization."""

from __future__ import annotations

from nd_mind_mirror.ui.window.main.legacy.editor_interaction_enhancements_legacy import (
    EditorInteractionEnhancements as LegacyEditorInteractionEnhancements,
)


class EditorInteractionEnhancements(LegacyEditorInteractionEnhancements):
    """Keep legacy UI integrations while leaving Source/Visual synchronization canonical."""

    @classmethod
    def install(cls) -> None:
        """Install compatibility features without replacing LaTeX mode-sync methods."""
        if cls._installed:
            return
        cls._install_terminal_noise_filter()
        cls._install_preview_search_noise_guard()
        cls._install_source_layout_window()
        cls._install_source_bookmark_menu()
        cls._install_visual_bookmark_menu()
        cls._install_visual_layout_fixes()
        cls._install_scroll_structure_sync()
        cls._installed = True
