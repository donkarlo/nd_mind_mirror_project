from pathlib import Path


class LatexPreviewSourceLocation:
    """One source position represented by a generated Preview line."""

    def __init__(
        self,
        source_path: str | Path,
        line: int,
        column: int = 1,
        preview_line: int = 1,
    ) -> None:
        self.source_path = Path(source_path).expanduser().resolve(strict=False)
        self.line = max(int(line), 1)
        self.column = max(int(column), 1)
        self.preview_line = max(int(preview_line), 1)
