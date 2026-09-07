from pathlib import Path

from nd_mind_mirror.core.latex.input.recursive.workspace_recursive_input_resolver import (
    WorkspaceRecursiveInputResolver,
)
from nd_mind_mirror.core.render.latex.diagnostic.latex_preview_source_map import (
    LatexPreviewSourceMap,
)
from nd_mind_mirror.core.render.latex.latex_preview_source_builder import (
    LatexPreviewSourceBuilder,
)


class LatexPreviewSourceMapBuilder:
    """Reproduce Preview expansion only to recover generated-line provenance."""

    def __init__(
        self,
        default_path: str | Path | None,
        template_path: str | Path,
        beamer_template_path: str | Path | None = None,
    ) -> None:
        self._input_resolver = WorkspaceRecursiveInputResolver(default_path)
        self._source_builder = LatexPreviewSourceBuilder(
            template_path,
            beamer_template_path=beamer_template_path,
        )

    def set_default_path(self, default_path: str | Path | None) -> None:
        self._input_resolver.set_default_path(default_path)

    def configure(
        self,
        default_path: str | Path | None,
        template_path: str | Path,
        beamer_template_path: str | Path | None = None,
    ) -> None:
        self._input_resolver.set_default_path(default_path)
        self._source_builder.set_template_path(template_path)
        self._source_builder.set_beamer_template_path(beamer_template_path)

    def build(
        self,
        source_path: str | Path,
        source: str,
    ) -> LatexPreviewSourceMap:
        path = Path(source_path).expanduser().resolve(strict=False)
        expanded = self._input_resolver.resolve(source, path)
        prepared = self._source_builder.build(
            source=expanded,
            source_path=path,
            title_source=source,
        )
        return LatexPreviewSourceMap(
            prepared_source=prepared,
            master_path=path,
            master_source=source,
        )
