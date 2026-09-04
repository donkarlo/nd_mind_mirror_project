"""Keep large-document optimizations that cannot replace the canonical Source text."""

from __future__ import annotations

from nd_mind_mirror.ui.window.main.large_document_performance_controller import (
    LargeDocumentPerformanceController,
)


class SafeLargeDocumentPerformanceController(LargeDocumentPerformanceController):
    """Install large-document optimizations while leaving Source text canonical and complete."""

    @classmethod
    def _install_runtime_patches(cls) -> None:
        """Install only optimizations that never window or replace the Source document."""
        if cls._runtime_installed:
            return

        cls._install_structure_idle_fast_path()
        cls._install_preview_fast_path()
        cls._install_preview_disable_cleanup()
        cls._install_navigator_density()
        cls._install_double_shift_focus_fix()
        cls._install_global_line_number_overlay()
        cls._runtime_installed = True
