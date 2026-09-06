"""Install the remaining safe performance policies that are not yet canonical."""

from __future__ import annotations

from nd_mind_mirror.ui.window.main.large_document_performance_controller import (
    LargeDocumentPerformanceController,
)


class SafeLargeDocumentPerformanceController(LargeDocumentPerformanceController):
    """Keep only legacy policies whose behavior has not yet moved into core classes."""

    @classmethod
    def _install_runtime_patches(cls) -> None:
        if cls._runtime_installed:
            return

        # Structure large-file handling now lives in LatexStructurePanel itself.
        # LogicalLineNumberOverlay also owns its canonical implementation.
        cls._install_preview_fast_path()
        cls._install_preview_disable_cleanup()
        cls._install_navigator_density()
        cls._install_double_shift_focus_fix()
        cls._runtime_installed = True
