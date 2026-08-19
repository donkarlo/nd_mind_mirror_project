from pathlib import Path


class Document:
    extension = ""

    def load(self, path: str | Path) -> str:
        raise NotImplementedError

    def save(self, path: str | Path, content: str) -> None:
        raise NotImplementedError
