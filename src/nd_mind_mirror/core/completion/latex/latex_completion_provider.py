from pathlib import Path


class LatexCompletionProvider:
    def load(self) -> list[str]:
        resource_path = self._find_resource()

        if resource_path is None:
            return [
                "\\documentclass{}",
                "\\usepackage{}",
                "\\begin{}",
                "\\end{}",
                "\\section{}",
                "\\subsection{}",
                "\\input{}",
                "\\include{}",
            ]

        try:
            lines = resource_path.read_text(
                encoding="utf-8"
            ).splitlines()
        except OSError:
            return []

        return sorted(
            {
                line.strip()
                for line in lines
                if line.strip()
                and not line.lstrip().startswith("#")
            }
        )

    def _find_resource(self) -> Path | None:
        current = Path(__file__).resolve()

        for parent in current.parents:
            candidate = parent / "resources" / "latex_completions.txt"

            if candidate.is_file():
                return candidate

        return None
