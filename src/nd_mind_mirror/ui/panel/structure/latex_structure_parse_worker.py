from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from nd_mind_mirror.core.latex.structure.latex_structure_parser import (
    LatexStructureParser,
)


class LatexStructureParseWorker(QThread):
    """Parse one complete LaTeX source outside the GUI thread."""

    parsed = Signal(int, object)
    failed = Signal(int, str)

    def __init__(
        self,
        generation: int,
        source: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._generation = int(generation)
        self._source = str(source)

    def run(self) -> None:
        try:
            structure = LatexStructureParser().parse(self._source)
        except Exception as exc:
            self.failed.emit(self._generation, str(exc))
            return
        self.parsed.emit(self._generation, structure)
