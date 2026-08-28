"""Final compile-safe normalizations for migration_4 generated Swift."""

from __future__ import annotations

from pathlib import Path


class IpadMigration4CompileFix:
    def __init__(self, source_root: str | Path) -> None:
        self.source_root = Path(source_root).expanduser().resolve()

    def apply(self) -> bool:
        path = self.source_root / "Views" / "PencilCanvasView.swift"
        if not path.is_file():
            return False
        original = path.read_text(encoding="utf-8")
        text = original.replace(
            '''            return PKStroke(
                ink: stroke.ink,
                transform: .identity,
                path: path
            )
''',
            '''            return PKStroke(
                ink: stroke.ink,
                path: path,
                transform: .identity,
                mask: stroke.mask
            )
''',
            1,
        )
        if text == original:
            return False
        path.write_text(text, encoding="utf-8")
        return True
