"""Build the canonical iPad Swift Playgrounds transfer ZIP without source duplication."""

from pathlib import Path
import re
import zipfile

from nd_mind_mirror.graphic.ipad.source_hotfix_migration import IpadSourceHotfixMigration
from nd_mind_mirror.graphic.ipad.source_post_hotfix import IpadSourcePostHotfix


class IpadPackageBuilder:
    """Apply idempotent current-source fixes and refresh the transfer archive."""

    _README_START = "<!-- ND_IPAD_CURRENT_FEATURES_START -->"
    _README_END = "<!-- ND_IPAD_CURRENT_FEATURES_END -->"
    _NUMBERED_PACKAGE_RE = re.compile(r"^nd_graphic \(\d+\)\.swiftpm$")

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.source = (
            self.project_root
            / "src"
            / "nd_mind_mirror"
            / "graphic"
            / "ipad"
            / "nd_graphic.swiftpm"
        )
        self.destination = self.source.parent / "nd_graphic.zip"

    def refresh(self) -> Path | None:
        if not self.source.is_dir():
            return None

        self._remove_numbered_package_copies()
        IpadSourceHotfixMigration(self.source).apply()
        IpadSourcePostHotfix(self.source).apply()
        self._sync_readme_features()

        source_files = sorted(path for path in self.source.rglob("*") if path.is_file())
        if not source_files:
            return None

        latest_source_ns = max(path.stat().st_mtime_ns for path in source_files)
        if self.destination.is_file() and self.destination.stat().st_mtime_ns >= latest_source_ns:
            return self.destination

        self.destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.destination.with_name(self.destination.name + ".tmp")
        temporary.unlink(missing_ok=True)
        with zipfile.ZipFile(
            temporary,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for path in source_files:
                archive.write(
                    path,
                    arcname=path.relative_to(self.source.parent).as_posix(),
                )
        temporary.replace(self.destination)
        return self.destination

    def _remove_numbered_package_copies(self) -> None:
        """Remove only file conflict copies named ``nd_graphic (N).swiftpm``."""
        try:
            candidates = tuple(self.source.parent.iterdir())
        except OSError:
            return

        for candidate in candidates:
            if not candidate.is_file():
                continue
            if self._NUMBERED_PACKAGE_RE.fullmatch(candidate.name) is None:
                continue
            try:
                candidate.unlink()
            except OSError:
                pass

    def _sync_readme_features(self) -> None:
        """Describe current capabilities only; never append per-version history."""
        readme = self.project_root / "README.md"
        if not readme.is_file():
            return
        try:
            text = readme.read_text(encoding="utf-8")
        except OSError:
            return

        block = (
            f"{self._README_START}\n"
            "### Current iPad graphic and preview features\n\n"
            "- LaTeX Structure includes `\\includegraphics` entries. A graphic inside a `figure` uses its `\\caption` text when present; otherwise Structure shows the image filename.\n"
            "- Preview Auto Fit fits the complete physical PDF page width once for a newly opened LaTeX document, keeps that zoom fixed during typing/live reloads, and never raster-scans pages to calculate fit.\n"
            "- Preview wheel/touchpad scrolling is handled directly by the PDF viewport. Source/Visual selection highlighting is applied only after the current SyncTeX mapping is ready, so highlighting does not control wheel scrolling or use stale PDF coordinates.\n"
            "- Live Preview cancels an obsolete LaTeX compile after the normal typing debounce and immediately renders the newest editor generation instead of waiting indefinitely for an old compile.\n"
            "- The canonical editable Swift Playgrounds package is `src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/`; startup removes numbered `nd_graphic (N).swiftpm` transfer/conflict copies and never treats them as source.\n"
            "- New Ubuntu `Insert image in iPad` graphics reuse the last edited iPad canvas size; both new and existing graphics open at logical 100% with the canvas aligned to the top-left viewport. Two-finger pinch zoom remains enabled after opening.\n"
            "- Starting the iPad app or reconnecting the bridge does not reopen a stale previous insert/update request and does not create a new blank graphic. Opening an insert request no longer performs an eager blank save before the user changes the canvas.\n"
            "- Existing update backgrounds are preserved during ordinary iPad autosaves even if SwiftUI briefly exposes a nil background while a document is loading, preventing a white canvas from overwriting the real PNG.\n"
            "- The iPad toolbar can keep any number of persistent Pencil and Highlighter tools. Saved tools store tool type, color, visible width, and opacity in `UserDefaults`; their toolbar buttons are icon-only, with icon color, visual weight/size, and alpha reflecting those saved settings.\n"
            "- Pencil and Highlighter width/opacity remain adjustable, but the toolbar no longer prints numeric thickness or transparency labels beside those controls.\n"
            "- Photos selected on iPad are inserted as editable image objects rather than replacing the document background. Image objects keep aspect ratio, start at a bounded top-left size, can be selected by finger or Apple Pencil Lasso, moved, proportionally resized, deleted, and support Undo/Redo for insert/delete/move/resize.\n"
            "- Editable image-object metadata is stored in the graphic sidecar and returned by the bridge on later Edit operations, while the Ubuntu/base background remains a separate layer. The saved PNG composites base background, image objects, and PencilKit strokes.\n"
            "- Lasso stroke selection keeps its four proportional resize handles and dedicated blue move handle for dragging the selected strokes, with Undo/Redo support.\n"
            "- Canvas width and height are not capped at the former 8192 px limit. Existing PencilKit strokes define the minimum safe canvas dimensions, and the iPad reports when a requested canvas would clip the graphic.\n"
            "- Custom canvas numeric fields request the ASCII-capable number pad so canvas dimensions are entered with English digits.\n"
            "- The iPad measurement Grid and centimeter Rulers have independent toolbar switches and remain view-only overlays.\n"
            "- PencilKit internal content geometry is synchronized with logical canvas resizing so the full A4 portrait drawing area accepts Apple Pencil input.\n"
            "- Tapping the active source/image identity opens the ten most recently edited graphics and can request any of them from the Ubuntu bridge.\n"
            "- The current canvas dimensions are shown at the top of the canvas-size menu rather than permanently occupying the status bar.\n"
            "- `Ctrl+Shift+Delete` deletes the file represented by the current editor tab, using the normal delete confirmation workflow.\n"
            "- Pinned tabs have close buttons; closing one explicitly unpins it and closes the file.\n"
            "- Preview Lock prevents Source/Visual synchronization from moving the PDF and preserves the current zoom/scroll view through live reloads.\n"
            "- Preview Extend hides Navigator and Source/Visual panes so Preview alone fills the main window, and restores the previous pane visibility when toggled off.\n"
            "- Auto Fit no longer performs delayed multi-pass zoom/recenter restoration after each reload; QML preserves the view directly, reducing preview jumps and UI stalls.\n"
            "- Visual mode accepts pasted clipboard images through the same managed-image insertion workflow as Source mode, while explicit LaTeX image widths continue to track the visible text width.\n"
            "- Navigator selection, rename, drag, bookmarks, autosave, and idle memory compaction remain enabled.\n"
            f"{self._README_END}"
        )

        updated = text.replace(
            "src/nd_mind_mirror/graphic/ipad/.source/nd_graphic.swiftpm/",
            "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/",
        )
        if self._README_START in updated and self._README_END in updated:
            start = updated.index(self._README_START)
            end = updated.index(self._README_END, start) + len(self._README_END)
            updated = updated[:start] + block + updated[end:]
        else:
            updated = updated.rstrip() + "\n\n" + block + "\n"

        if updated != text:
            try:
                readme.write_text(updated, encoding="utf-8")
            except OSError:
                pass
