from pathlib import Path


class InputResolver:
    def resolve(self, source: str, source_path: Path | None) -> str:
        raise NotImplementedError
