"""Keep the Structure panel visually limited to one active section."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSignalBlocker, QTimer

from nd_mind_mirror.ui.window.main.structure_highlight_controller import (
    StructureHighlightController,
)


class StructureSelectionIntegrityController:
    """Prevent stale Qt current/selection state from painting a second row."""

    _installed = False
    _original_init: Callable | None = None
    _original_apply_highlight: Callable | None = None

    @classmethod
    def install(cls) -> None:
        """Strengthen StructureHighlightController before its first instance exists."""
        if cls._installed:
            return

        cls._original_init = StructureHighlightController.__init__
        cls._original_apply_highlight = StructureHighlightController.apply_highlight

        def controller_init(controller, structure_panel) -> None:
            cls._original_init(controller, structure_panel)
            controller._nd_selection_integrity_running = False
            controller._nd_selection_integrity_scheduled = False
            tree = structure_panel._tree
            tree.currentItemChanged.connect(
                lambda *_args, item=controller: cls._schedule_reapply(item)
            )
            tree.itemSelectionChanged.connect(
                lambda item=controller: cls._schedule_reapply(item)
            )

        def apply_highlight(controller) -> None:
            if bool(getattr(controller, "_nd_selection_integrity_running", False)):
                return

            controller._nd_selection_integrity_running = True
            tree = controller._panel._tree
            blocker = QSignalBlocker(tree)
            try:
                cls._original_apply_highlight(controller)
                tree.clearSelection()
                tree.setCurrentItem(None)
                selection_model = tree.selectionModel()
                if selection_model is not None:
                    selection_model.clear()
            finally:
                del blocker
                controller._nd_selection_integrity_running = False
            tree.viewport().update()

        StructureHighlightController.__init__ = controller_init
        StructureHighlightController.apply_highlight = apply_highlight
        cls._installed = True

    @classmethod
    def _schedule_reapply(cls, controller: StructureHighlightController) -> None:
        if bool(getattr(controller, "_nd_selection_integrity_scheduled", False)):
            return
        controller._nd_selection_integrity_scheduled = True
        QTimer.singleShot(
            0,
            lambda item=controller: cls._reapply(item),
        )

    @staticmethod
    def _reapply(controller: StructureHighlightController) -> None:
        controller._nd_selection_integrity_scheduled = False
        controller.apply_highlight()
