"""Compatibility controller for the canonical Pinned/Open proxy tab rows."""

from nd_mind_mirror.ui.window.main.pinned_tab_controller import (
    PinnedTabController,
)


class StablePinnedTabController(PinnedTabController):
    """Use the canonical proxy rows without any custom tab-list dropdown."""
