"""Current iPad release wrapper and post-hotfix normalizer."""
from __future__ import annotations

from .source_post_hotfix_core import IpadSourcePostHotfix as _Core
from .source_dynamic_legacy_cleanup import IpadDynamicLegacyCleanup
from .source_dynamic_content_patch import IpadDynamicContentPatch
from .source_toolbar_management_patch import IpadToolbarManagementPatch
from .source_dynamic_canvas_patch import IpadDynamicCanvasPatch
from .source_release_compile_normalizer import IpadReleaseCompileNormalizer


class IpadSourcePostHotfix(_Core):
    RELEASE_VERSION = "0.31.19"
    RELEASE_BUILD = "49"

    def apply(self) -> bool:
        changed = False
        changed |= self._patch_release_version()
        changed |= self._patch_pinch_zoom()
        changed |= self._patch_selection_move_handle()
        changed |= IpadDynamicLegacyCleanup(self.source_root).apply()
        changed |= IpadDynamicContentPatch(self.source_root).apply()
        changed |= IpadToolbarManagementPatch(self.source_root).apply()
        changed |= IpadDynamicCanvasPatch(self.source_root).apply()
        changed |= IpadReleaseCompileNormalizer(self.source_root).apply()
        return changed
