"""Build the canonical iPad Swift Playgrounds transfer ZIP."""

from __future__ import annotations

from pathlib import Path
import re
import zipfile


class IpadPackageBuilder:
    """Package the canonical Swift source without mutating application source."""

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
        """Rebuild the ZIP only when canonical Swift source is newer."""
        if not self.source.is_dir():
            return None

        self._remove_numbered_package_copies()
        source_files = tuple(
            sorted(path for path in self.source.rglob("*") if path.is_file())
        )
        if not source_files:
            return None

        latest_source_ns = max(path.stat().st_mtime_ns for path in source_files)
        if (
            self.destination.is_file()
            and self.destination.stat().st_mtime_ns >= latest_source_ns
        ):
            return self.destination

        self.destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.destination.with_suffix(self.destination.suffix + ".tmp")
        temporary.unlink(missing_ok=True)
        try:
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
        finally:
            temporary.unlink(missing_ok=True)
        return self.destination

    def _remove_numbered_package_copies(self) -> None:
        """Remove Dropbox conflict copies of the transfer package only."""
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
