from hashlib import sha256
from pathlib import Path
import shutil

from PySide6.QtCore import Signal

from nd_mind_mirror.core.latex.input.recursive.workspace_recursive_input_resolver import (
    WorkspaceRecursiveInputResolver,
)
from nd_mind_mirror.core.render.latex.diagnostic.latex_bibliography_process_result_classifier import (
    LatexBibliographyProcessResultClassifier,
)
from nd_mind_mirror.core.render.latex.diagnostic.latex_compiler_diagnostic_extractor import (
    LatexCompilerDiagnosticExtractor,
)
from nd_mind_mirror.core.render.latex.latex_renderer_base import (
    LatexRenderer as BaseLatexRenderer,
)
from nd_mind_mirror.graphic.core.workspace_graphic_dependency_resolver import (
    WorkspaceGraphicDependencyResolver,
)


class LatexRenderer(BaseLatexRenderer):
    """Add profile-aware configuration and a last-valid-PDF cache per source file."""

    cached_preview_available = Signal(str)
    preview_source_empty = Signal(str)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # Preview must always use the same path modes as workspace navigation
        # and refactoring. The configured root is injected before session
        # restore, but the renderer owns workspace-aware resolvers from birth.
        self._input_resolver = WorkspaceRecursiveInputResolver()
        self._graphic_dependency_resolver = WorkspaceGraphicDependencyResolver()
        self._diagnostic_extractor = LatexCompilerDiagnosticExtractor()
        self._bibliography_process_result_classifier = (
            LatexBibliographyProcessResultClassifier()
        )
        self._source_preview_cache_dir = self._temp_dir / "source_preview_cache"
        self._source_preview_cache_dir.mkdir(parents=True, exist_ok=True)
        self._last_valid_pdf_by_source: dict[Path, Path] = {}
        self._visible_source_path: Path | None = None
        self._preview_profile_signature: tuple[str, ...] | None = None

    def set_workspace_default_path(
        self,
        default_path: str | Path | None,
    ) -> None:
        """Keep Preview input and graphic lookup rooted at search.default_path."""
        self._input_resolver.set_default_path(default_path)
        self._graphic_dependency_resolver.set_default_path(default_path)

    def configure_preview_profiles(
        self,
        *,
        active_profile: str,
        default_template_path: str | Path,
        graph_template_path: str | Path,
        german_template_path: str | Path,
        beamer_template_path: str | Path,
    ) -> None:
        signature = (
            str(active_profile),
            str(Path(default_template_path).expanduser().resolve()),
            str(Path(graph_template_path).expanduser().resolve()),
            str(Path(german_template_path).expanduser().resolve()),
            str(Path(beamer_template_path).expanduser().resolve()),
        )
        self._preview_source_builder.configure_profiles(
            active_profile=active_profile,
            default_template_path=default_template_path,
            graph_template_path=graph_template_path,
            german_template_path=german_template_path,
            beamer_template_path=beamer_template_path,
        )
        if signature != self._preview_profile_signature:
            self._preview_profile_signature = signature
            self.invalidate_preview_cache()

    def invalidate_preview_cache(self) -> None:
        self._last_valid_pdf_by_source.clear()
        self._visible_source_path = None
        shutil.rmtree(self._source_preview_cache_dir, ignore_errors=True)
        self._source_preview_cache_dir.mkdir(parents=True, exist_ok=True)

    def render(
        self,
        source: str,
        source_path: str | Path | None = None,
        immediate: bool = False,
    ) -> None:
        target = self._resolved_source_path(source_path)
        if target != self._visible_source_path:
            self._visible_source_path = target
            cached = (
                self._last_valid_pdf_by_source.get(target)
                if target is not None
                else None
            )
            if cached is not None and cached.is_file():
                self.cached_preview_available.emit(str(cached))
            else:
                self.preview_source_empty.emit(
                    str(target) if target is not None else ""
                )
        super().render(
            source,
            source_path=source_path,
            immediate=immediate,
        )

    def _extract_useful_error(self, output: str) -> str:
        """Return actionable compiler diagnostics without dropping error context."""
        return self._diagnostic_extractor.extract(output)

    def _emit_compile_failure(self) -> None:
        """Continue past warning-only bibliography exits; fail on real errors."""
        if self._bibliography_process_result_classifier.is_recoverable_warning_exit(
            phase=self._phase,
            output=self._last_process_output,
        ):
            self._start_lualatex("latex2")
            return
        super()._emit_compile_failure()

    def _publish_current_pdf(self) -> bool:
        published = super()._publish_current_pdf()
        if published:
            self._remember_current_source_pdf()
        return published

    def _remember_current_source_pdf(self) -> None:
        source_path = getattr(self, "_cache_source_path", None)
        if source_path is None or not self._pdf_path.is_file():
            return
        resolved = Path(source_path).expanduser().resolve()
        digest = sha256(str(resolved).encode("utf-8")).hexdigest()[:24]
        destination = self._source_preview_cache_dir / f"{digest}.pdf"
        try:
            shutil.copy2(self._pdf_path, destination)
        except OSError:
            return
        self._last_valid_pdf_by_source[resolved] = destination

    def _resolved_source_path(
        self,
        source_path: str | Path | None,
    ) -> Path | None:
        candidate = source_path
        if candidate is None:
            candidate = getattr(self, "_source_path", None)
        if candidate in (None, ""):
            return None
        try:
            return Path(candidate).expanduser().resolve()
        except (OSError, TypeError, ValueError):
            return None
