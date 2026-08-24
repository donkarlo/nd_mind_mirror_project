"""Build the iPad Swift Playgrounds transfer ZIP from the visible editable Swift package source."""

from pathlib import Path
import zipfile

from nd_mind_mirror.graphic.ipad.source_migration import IpadSourceMigration
from nd_mind_mirror.graphic.ipad.source_hotfix_migration import IpadSourceHotfixMigration


class IpadPackageBuilder:
    """Keep editable iPad source migrated and refresh the transfer archive when needed."""

    _README_START = "<!-- ND_IPAD_CURRENT_FEATURES_START -->"
    _README_END = "<!-- ND_IPAD_CURRENT_FEATURES_END -->"

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

        # Keep the older idempotent migration first, then apply the current
        # behavior hotfixes so the legacy migration cannot overwrite them.
        IpadSourceMigration(self.source).apply()
        IpadSourceHotfixMigration(self.source).apply()
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

    def _sync_readme_features(self) -> None:
        """Keep README focused on current capabilities rather than version history."""
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
            "- The canonical editable Swift Playgrounds package is visible at `src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/`; there is no separate hidden Swift source project.\n"
            "- The native iPad graphic editor shows `source.tex > image.png` for the active managed figure.\n"
            "- New managed iPad graphics use an A4 portrait canvas (1240 × 1754 px); the A4 portrait preset remains available for existing graphics.\n"
            "- The iPad canvas has a visible 0.5 cm measurement grid plus numbered top and left centimeter rulers; the overlay is view-only and is never rendered into the saved PNG.\n"
            "- Resizing the logical canvas preserves the current PencilKit drawing and background image instead of forcing a document reload.\n"
            "- Editing an ordinary existing PNG on iPad preserves that PNG as the initial background when its sidecar has no PencilKit/background payload, so opening it no longer produces a blank white canvas.\n"
            "- The recent-color grid opens as a floating popover anchored to its toolbar button, does not push the canvas, and closes automatically after a color is selected.\n"
            "- The iPad zoom menu includes an explicit 100% command that sets the PencilKit viewport to logical zoom scale 1.0 and recenters the canvas.\n"
            "- Navigator reveal operations avoid scrolling when the requested item is already visible, preserve pixel scroll offsets across proxy relayouts, and keep rename/drag viewport position stable.\n"
            "- Visual mode accepts pasted clipboard images by routing them through the same managed-image insertion path as Source mode.\n"
            "- Bookmark Go To waits for the target tab to become active before positioning the cursor.\n"
            "- Preview edit highlighting keeps the last non-empty selection visible across Source/Visual/Preview switches.\n"
            "- Delete confirmation focuses Yes for immediate keyboard confirmation while keeping the existing confirmation dialog.\n"
            "- Idle memory compaction periodically releases unused Python/glibc heap pages without disabling editor features.\n"
            "- Ubuntu uses one `Preview` button as the preview open/close toggle; the old × control is hidden and the active button has a light-gray background.\n"
            "- Visual mode sizes `\\includegraphics[width=N\\textwidth|\\linewidth|\\columnwidth]` images from the visible text width and reapplies the size after layout/resize changes.\n"
            f"{self._README_END}"
        )

        updated = text
        updated = updated.replace(
            "src/nd_mind_mirror/graphic/ipad/.source/nd_graphic.swiftpm/",
            "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/",
        )
        updated = updated.replace(
            "generated automatically from the hidden source package",
            "generated automatically from the visible editable source package",
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
                return
