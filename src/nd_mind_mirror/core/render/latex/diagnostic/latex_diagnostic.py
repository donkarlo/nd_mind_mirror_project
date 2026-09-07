from nd_mind_mirror.core.render.latex.diagnostic.latex_diagnostic_node import (
    LatexDiagnosticNode,
)


class LatexDiagnostic:
    """Structured Preview failure with a human-readable dependency trace."""

    def __init__(
        self,
        summary: str,
        raw_message: str,
        root: LatexDiagnosticNode,
    ) -> None:
        self.summary = str(summary).strip() or "LaTeX compilation failed."
        self.raw_message = str(raw_message).strip()
        self.root = root
