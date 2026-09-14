from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import shutil
import tempfile


@dataclass(frozen=True)
class LatexBuildGeneration:
    generation: int
    source_path: Path | None
    directory: Path

    @property
    def tex_path(self) -> Path:
        return self.directory / "preview.tex"

    @property
    def pdf_path(self) -> Path:
        return self.directory / "preview.pdf"

    @property
    def synctex_path(self) -> Path:
        return self.directory / "preview.synctex.gz"


class LatexBuildWorkspace:
    """Own isolated preview-build generations and validated auxiliary snapshots.

    A compiler process writes only into its generation directory. A canceled or
    failed generation is therefore never a source of incremental state for a
    later generation. Reusable LaTeX auxiliary files are copied only from the
    latest explicit checkpoint created after a successful subprocess exit.
    """

    _AUXILIARY_FILENAMES = (
        "preview.aux",
        "preview.bbl",
        "preview.blg",
        "preview.toc",
        "preview.out",
        "preview.nav",
        "preview.snm",
        "preview.bcf",
        "preview.run.xml",
    )

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = (
            Path(root).expanduser().resolve()
            if root is not None
            else Path(tempfile.mkdtemp(prefix="nd_mind_mirror_"))
        )
        self.root.mkdir(parents=True, exist_ok=True)
        self._build_root = self.root / "builds"
        self._aux_cache_root = self.root / "aux_cache"
        self._published_root = self.root / "published"
        self._build_root.mkdir(parents=True, exist_ok=True)
        self._aux_cache_root.mkdir(parents=True, exist_ok=True)
        self._published_root.mkdir(parents=True, exist_ok=True)
        self._active: LatexBuildGeneration | None = None
        self._published_paths: list[Path] = []

    @property
    def active(self) -> LatexBuildGeneration:
        if self._active is None:
            raise RuntimeError("No active LaTeX build generation.")
        return self._active

    def start_generation(
        self,
        generation: int,
        source_path: str | Path | None,
    ) -> LatexBuildGeneration:
        resolved_source = self._resolve_source_path(source_path)
        directory = self._build_root / f"generation_{int(generation):08d}"
        shutil.rmtree(directory, ignore_errors=True)
        directory.mkdir(parents=True, exist_ok=True)

        self._seed_auxiliary_snapshot(directory, resolved_source)
        self._active = LatexBuildGeneration(
            generation=int(generation),
            source_path=resolved_source,
            directory=directory,
        )
        self._prune_build_directories(keep=4)
        return self._active

    def checkpoint_auxiliary(self) -> bool:
        active = self.active
        destination = self._auxiliary_cache_dir(active.source_path)
        staging = destination.with_name(destination.name + ".staging")
        try:
            shutil.rmtree(staging, ignore_errors=True)
            staging.mkdir(parents=True, exist_ok=True)
            for name in self._AUXILIARY_FILENAMES:
                source = active.directory / name
                if source.is_file():
                    shutil.copy2(source, staging / name)
            shutil.rmtree(destination, ignore_errors=True)
            staging.replace(destination)
        except OSError:
            shutil.rmtree(staging, ignore_errors=True)
            return False
        return True

    def reset_active_outputs(self, keep_tex: bool = True) -> None:
        active = self.active
        for path in active.directory.iterdir():
            if keep_tex and path == active.tex_path:
                continue
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
                continue
            try:
                path.unlink()
            except OSError:
                pass

    def publish_pdf(self, generation: int, sequence: int) -> Path | None:
        source = self.active.pdf_path
        if not source.is_file():
            return None
        destination = self._published_root / (
            f"preview_render_{int(generation):08d}_{int(sequence):08d}.pdf"
        )
        try:
            shutil.copy2(source, destination)
        except OSError:
            return None
        self._published_paths.append(destination)
        self._prune_published_pdfs(keep=8)
        return destination

    def _seed_auxiliary_snapshot(
        self,
        destination: Path,
        source_path: Path | None,
    ) -> None:
        cache = self._auxiliary_cache_dir(source_path)
        if not cache.is_dir():
            return
        for name in self._AUXILIARY_FILENAMES:
            source = cache / name
            if source.is_file():
                shutil.copy2(source, destination / name)

    def _auxiliary_cache_dir(self, source_path: Path | None) -> Path:
        key_source = str(source_path) if source_path is not None else "<unsaved>"
        digest = sha256(key_source.encode("utf-8")).hexdigest()[:24]
        return self._aux_cache_root / digest

    def _resolve_source_path(
        self,
        source_path: str | Path | None,
    ) -> Path | None:
        if source_path in (None, ""):
            return None
        return Path(source_path).expanduser().resolve()

    def _prune_build_directories(self, keep: int) -> None:
        active_dir = self._active.directory if self._active is not None else None
        directories = sorted(
            (path for path in self._build_root.iterdir() if path.is_dir()),
            key=lambda path: path.name,
        )
        removable = [path for path in directories if path != active_dir]
        while len(removable) > max(keep - 1, 0):
            stale = removable.pop(0)
            shutil.rmtree(stale, ignore_errors=True)

    def _prune_published_pdfs(self, keep: int) -> None:
        while len(self._published_paths) > keep:
            stale = self._published_paths.pop(0)
            try:
                stale.unlink()
            except OSError:
                pass
