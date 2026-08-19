from pathlib import Path

from nd_mind_mirror.core.document.base.document import Document


class LatexDocument(Document):
    extension = ".tex"

    def load(self, path: str | Path) -> str:
        file_path = Path(path).expanduser().resolve()

        if file_path.suffix.lower() != self.extension:
            raise ValueError("Only .tex files can be opened.")

        try:
            return file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return file_path.read_text(encoding="latin-1")

    def save(self, path: str | Path, content: str) -> None:
        file_path = Path(path).expanduser().resolve()
        file_path.write_text(content, encoding="utf-8")
