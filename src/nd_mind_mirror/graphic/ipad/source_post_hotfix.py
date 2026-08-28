"""Current iPad release wrapper and post-hotfix normalizer."""
from __future__ import annotations

from pathlib import Path
import re

from .source_post_hotfix_core import IpadSourcePostHotfix as _Core
from .source_dynamic_legacy_cleanup import IpadDynamicLegacyCleanup
from .source_dynamic_content_patch import IpadDynamicContentPatch
from .source_toolbar_management_patch import IpadToolbarManagementPatch
from .source_dynamic_canvas_patch import IpadDynamicCanvasPatch
from .source_release_compile_normalizer import IpadReleaseCompileNormalizer
from .source_migration_4_compile_fix import IpadMigration4CompileFix


def _repair_migration4_sources() -> None:
    """Repair migration-4 source issues before desktop modules are imported."""
    project_root = Path(__file__).resolve().parents[4]

    patch_path = Path(__file__).with_name("source_migration_4_patch.py")
    if patch_path.is_file():
        original = patch_path.read_text(encoding="utf-8")
        updated = original.replace(
            '"The shortcut file was not overwritten.\\n\\n" + message,',
            '"The shortcut file was not overwritten.\\\\n\\\\n" + message,',
        )
        if updated != original:
            patch_path.write_text(updated, encoding="utf-8")

    main_window_path = (
        project_root
        / "src"
        / "nd_mind_mirror"
        / "ui"
        / "window"
        / "main"
        / "main_window.py"
    )
    if main_window_path.is_file():
        original = main_window_path.read_text(encoding="utf-8")
        updated = original.replace(
            '"The shortcut file was not overwritten.\n\n" + message,',
            '"The shortcut file was not overwritten.\\n\\n" + message,',
        )
        if updated != original:
            main_window_path.write_text(updated, encoding="utf-8")


def _repair_preview_pipeline() -> None:
    """Keep first preview publication fast and prevent endless rendering."""
    project_root = Path(__file__).resolve().parents[4]

    enhanced_path = (
        project_root
        / "src"
        / "nd_mind_mirror"
        / "ui"
        / "window"
        / "main"
        / "enhanced_main_window.py"
    )
    if enhanced_path.is_file():
        original = enhanced_path.read_text(encoding="utf-8")
        aggressive = '''            if (
                len(source) < self._SMALL_PREVIEW_SOURCE_CHARS
                and renderer._process.state()
                != QProcess.ProcessState.NotRunning
            ):
                pending = int(getattr(renderer, "_pending_generation", 0))
                active = int(getattr(renderer, "_active_generation", 0))
                latest = int(getattr(renderer, "_latest_requested_generation", 0))
                if pending > active or latest > active:
                    renderer._stop_running_process()
                else:
                    return

            base_compile_pending_source()
'''
        coalesced = '''            # ND_FAST_PREVIEW_COALESCE
            # Never kill a healthy small-file compile because another startup
            # signal arrived. The renderer already coalesces queued generations
            # and starts only the newest one when the active process finishes.
            base_compile_pending_source()
'''
        updated = original.replace(aggressive, coalesced, 1)
        if updated != original:
            enhanced_path.write_text(updated, encoding="utf-8")

    renderer_path = (
        project_root
        / "src"
        / "nd_mind_mirror"
        / "core"
        / "render"
        / "latex"
        / "latex_renderer.py"
    )
    if not renderer_path.is_file():
        return

    original = renderer_path.read_text(encoding="utf-8")
    updated = original

    if "ND_PREVIEW_COMPILE_WATCHDOG" not in updated:
        timer_anchor = '''        self._sync_timer.timeout.connect(
            self._map_pending_source_position
        )
'''
        timer_block = timer_anchor + '''
        # ND_PREVIEW_COMPILE_WATCHDOG
        # External TeX/BibTeX processes must never leave the UI in Rendering
        # forever. Fifteen seconds is deliberately generous for live preview;
        # export-quality work can still use the explicit Export PDF workflow.
        self._compile_watchdog = QTimer(self)
        self._compile_watchdog.setSingleShot(True)
        self._compile_watchdog.setInterval(15_000)
        self._compile_watchdog.timeout.connect(
            self._on_compile_timeout
        )
'''
        updated = updated.replace(timer_anchor, timer_block, 1)

        start_anchor = '''        self._process.setArguments(arguments)
        self._process.start()
'''
        start_block = '''        self._process.setArguments(arguments)
        self._process.start()
        self._compile_watchdog.start()
'''
        updated = updated.replace(start_anchor, start_block, 1)

        finished_anchor = '''    def _on_process_finished(
        self,
        exit_code: int,
        exit_status,
    ) -> None:
        if self._suppress_finished:
'''
        finished_block = '''    def _on_process_finished(
        self,
        exit_code: int,
        exit_status,
    ) -> None:
        self._compile_watchdog.stop()
        if self._suppress_finished:
'''
        updated = updated.replace(finished_anchor, finished_block, 1)

        stop_anchor = '''        self._suppress_finished = True
        self._process.kill()
'''
        stop_block = '''        self._compile_watchdog.stop()
        self._suppress_finished = True
        self._process.kill()
'''
        updated = updated.replace(stop_anchor, stop_block, 1)

        method_anchor = '''    def _stop_running_process(self) -> None:
'''
        timeout_method = '''    def _on_compile_timeout(self) -> None:
        """Abort a stuck preview subprocess and move on to the newest request."""
        if (
            self._process.state()
            == QProcess.ProcessState.NotRunning
        ):
            return

        phase = self._phase or "latex"
        self._suppress_finished = True
        self._process.kill()
        self._process.waitForFinished(1000)
        self._suppress_finished = False

        if self._is_current_generation():
            self.failed.emit(
                f"Preview {phase} timed out after 15 seconds."
            )

        if self._pending_generation > self._active_generation:
            QTimer.singleShot(0, self._compile_pending_source)

'''
        updated = updated.replace(method_anchor, timeout_method + method_anchor, 1)

    if "ND_FAST_FIRST_PASS_PUBLISH" not in updated:
        phase_pattern = re.compile(
            r'        if self\._phase == "latex1":\n.*?'
            r'\n        if self\._phase in \{"bibtex", "biber"\}:',
            re.DOTALL,
        )
        phase_replacement = '''        if self._phase == "latex1":
            # ND_FAST_FIRST_PASS_PUBLISH
            # Publish the first successful PDF immediately. Bibliography and
            # reference-settling passes continue only after the user already
            # has a visible preview.
            if not self._publish_current_pdf():
                self._emit_compile_failure()
                return

            bibliography_status = self._start_bibliography_tool()
            if bibliography_status == "started":
                return
            if bibliography_status == "missing":
                return

            if self._needs_latex_rerun(output):
                self._start_lualatex("latex2")
            return

        if self._phase in {"bibtex", "biber"}:'''
        updated, _count = phase_pattern.subn(phase_replacement, updated, count=1)

    if updated != original:
        renderer_path.write_text(updated, encoding="utf-8")


_repair_migration4_sources()
_repair_preview_pipeline()

from .source_migration_4_patch import ProjectMigration4Patch, IpadMigration4Patch


# package_builder is imported before the desktop Qt window modules. Apply the
# desktop/bridge source migrations now so this same application launch imports
# the corrected implementations rather than requiring a second restart.
ProjectMigration4Patch(Path(__file__).resolve().parents[4]).apply()


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
        changed |= IpadMigration4Patch(self.source_root).apply()
        changed |= IpadMigration4CompileFix(self.source_root).apply()
        changed |= IpadReleaseCompileNormalizer(self.source_root).apply()
        return changed
