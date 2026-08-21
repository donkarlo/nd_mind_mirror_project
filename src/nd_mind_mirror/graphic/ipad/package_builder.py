"""Build the iPad Swift Playgrounds transfer ZIP from the hidden editable Swift package source."""

from pathlib import Path
import zipfile


class IpadPackageBuilder:
    """Generate nd_graphic.zip only when the editable Swift package is newer than the transfer archive."""

    def __init__(self, project_root: str | Path) -> None:
        """Resolve the hidden source package and public transfer archive paths from the project root."""
        root = Path(project_root).expanduser().resolve()
        self.source = (
            root
            / "src"
            / "nd_mind_mirror"
            / "graphic"
            / "ipad"
            / ".source"
            / "nd_graphic.swiftpm"
        )
        self.destination = self.source.parent.parent / "nd_graphic.zip"

    def refresh(self) -> Path | None:
        """Rebuild the ZIP atomically when any Swift-package file is newer than the existing archive."""
        if not self.source.is_dir():
            return None
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
