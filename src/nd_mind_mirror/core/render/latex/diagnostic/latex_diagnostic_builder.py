from pathlib import Path
import re

from nd_mind_mirror.core.render.latex.diagnostic.latex_diagnostic import (
    LatexDiagnostic,
)
from nd_mind_mirror.core.render.latex.diagnostic.latex_diagnostic_node import (
    LatexDiagnosticNode,
)
from nd_mind_mirror.core.render.latex.diagnostic.latex_preview_source_map_builder import (
    LatexPreviewSourceMapBuilder,
)
from nd_mind_mirror.core.workspace.path.workspace_reference_resolver import (
    WorkspaceReferenceResolver,
)


class LatexDiagnosticBuilder:
    """Build a clickable include/input trace using canonical workspace semantics."""

    _UNRESOLVED_PATTERN = re.compile(
        r"(?P<path>/[^\n:]+\.(?:tex|tikz)):\s*"
        r"could not resolve\s+\\(?P<command>input|include)"
        r"\{(?P<target>[^{}]+)\}"
    )
    _FILE_LINE_PATTERN = re.compile(
        r"(?P<path>(?:[A-Za-z]:)?/[^\n:]+\.(?:tex|tikz)):"
        r"(?P<line>\d+)(?::(?P<column>\d+))?"
    )
    _FILE_NOT_FOUND_PATTERN = re.compile(
        r"File\s+[`'](?P<target>[^`']+)[`']\s+not found",
        re.IGNORECASE,
    )

    def __init__(
        self,
        default_path: str | Path | None,
        template_path: str | Path | None = None,
        beamer_template_path: str | Path | None = None,
    ) -> None:
        self._resolver = WorkspaceReferenceResolver(default_path)
        self._source_map_builder = (
            LatexPreviewSourceMapBuilder(
                default_path=default_path,
                template_path=template_path,
                beamer_template_path=beamer_template_path,
            )
            if template_path not in (None, "")
            else None
        )
        self._edge_nodes: dict[tuple[str, str, str], LatexDiagnosticNode] = {}
        self._file_nodes: dict[str, LatexDiagnosticNode] = {}

    def configure(
        self,
        default_path: str | Path | None,
        template_path: str | Path | None = None,
        beamer_template_path: str | Path | None = None,
    ) -> None:
        self._resolver.set_default_path(default_path)
        if template_path in (None, ""):
            self._source_map_builder = None
            return
        if self._source_map_builder is None:
            self._source_map_builder = LatexPreviewSourceMapBuilder(
                default_path=default_path,
                template_path=template_path,
                beamer_template_path=beamer_template_path,
            )
            return
        self._source_map_builder.configure(
            default_path=default_path,
            template_path=template_path,
            beamer_template_path=beamer_template_path,
        )

    def set_default_path(self, default_path: str | Path | None) -> None:
        self._resolver.set_default_path(default_path)
        if self._source_map_builder is not None:
            self._source_map_builder.set_default_path(default_path)

    def build(
        self,
        message: str,
        source_path: str | Path,
        source: str,
    ) -> LatexDiagnostic:
        master_path = Path(source_path).expanduser().resolve(strict=False)
        self._edge_nodes = {}
        self._file_nodes = {}

        root = LatexDiagnosticNode(
            "search.default_path",
            self._display_path(self._resolver.default_path),
            "workspace",
        )
        master = LatexDiagnosticNode(
            self._relative_display(master_path),
            "Preview entry file",
            "file",
            source_path=master_path,
        )
        root.add_child(master)
        self._file_nodes[str(master_path)] = master

        self._walk_inputs(
            source=source,
            containing_file=master_path,
            parent_node=master,
            stack={master_path},
        )

        source_map = self._build_source_map(master_path, source)
        matched_error = self._mark_unresolved_errors(message)
        matched_error = self._mark_file_line_errors(message, source_map) or matched_error
        matched_error = self._mark_missing_file_error(message) or matched_error

        if not matched_error:
            master.add_child(
                LatexDiagnosticNode(
                    "Compilation error",
                    self._primary_message(message),
                    "error",
                    source_path=master_path,
                )
            )

        self._append_compiler_output(root, message)
        return LatexDiagnostic(
            summary=self._primary_message(message),
            raw_message=message,
            root=root,
        )

    def _build_source_map(self, source_path: Path, source: str):
        if self._source_map_builder is None:
            return None
        try:
            return self._source_map_builder.build(source_path, source)
        except (OSError, ValueError, RuntimeError):
            return None

    def _walk_inputs(
        self,
        source: str,
        containing_file: Path,
        parent_node: LatexDiagnosticNode,
        stack: set[Path],
    ) -> None:
        for occurrence in self._resolver.occurrences(
            source,
            containing_file,
            require_exists=False,
        ):
            if occurrence.command not in {"input", "include"}:
                continue

            target = self._resolver.resolve(
                occurrence.raw_target,
                containing_file,
                command=occurrence.command,
                require_exists=True,
            )
            candidate = occurrence.target_path
            edge = LatexDiagnosticNode(
                f"\\{occurrence.command}{{{occurrence.raw_target}}}",
                self._edge_detail(target, candidate),
                "reference" if target is not None else "missing",
                source_path=containing_file,
                line=occurrence.line,
                column=occurrence.column,
                target_path=target or candidate,
            )
            parent_node.add_child(edge)
            self._edge_nodes[
                (
                    str(containing_file),
                    occurrence.command,
                    occurrence.raw_target.strip(),
                )
            ] = edge

            if target is None:
                edge.add_child(
                    LatexDiagnosticNode(
                        "Candidate path",
                        self._display_path(candidate),
                        "missing",
                        source_path=containing_file,
                        line=occurrence.line,
                        column=occurrence.column,
                        target_path=candidate,
                    )
                )
                continue

            resolved = target.expanduser().resolve(strict=False)
            child = LatexDiagnosticNode(
                resolved.name,
                self._relative_display(resolved),
                "file",
                source_path=resolved,
            )
            edge.add_child(child)
            self._file_nodes[str(resolved)] = child

            if resolved in stack:
                child.kind = "warning"
                child.detail = (
                    "Recursive reference skipped — "
                    f"{self._relative_display(resolved)}"
                )
                continue

            nested_source = self._read_text(resolved)
            if nested_source is None:
                child.kind = "error"
                child.detail = "Resolved path exists but could not be read as text."
                continue

            nested_stack = set(stack)
            nested_stack.add(resolved)
            self._walk_inputs(
                source=nested_source,
                containing_file=resolved,
                parent_node=child,
                stack=nested_stack,
            )

    def _mark_unresolved_errors(self, message: str) -> bool:
        matched = False
        for match in self._UNRESOLVED_PATTERN.finditer(message):
            path = Path(match.group("path")).expanduser().resolve(strict=False)
            key = (
                str(path),
                match.group("command"),
                match.group("target").strip(),
            )
            node = self._edge_nodes.get(key)
            if node is None:
                continue
            node.mark_error(
                "Could not resolve this reference with the configured path rules."
            )
            matched = True
        return matched

    def _mark_file_line_errors(self, message: str, source_map) -> bool:
        matched = False
        seen: set[tuple[str, int, int]] = set()
        for match in self._FILE_LINE_PATTERN.finditer(message):
            reported_path = Path(match.group("path")).expanduser().resolve(strict=False)
            reported_line = max(int(match.group("line")), 1)
            reported_column = max(int(match.group("column") or 1), 1)

            mapped_from_preview = False
            path = reported_path
            line = reported_line
            column = reported_column
            if self._is_preview_temporary_path(reported_path):
                if source_map is None:
                    continue
                location = source_map.location_for_preview_line(reported_line)
                path = location.source_path
                line = location.line
                column = location.column
                mapped_from_preview = True

            file_node = self._file_nodes.get(str(path))
            if file_node is None:
                continue
            key = (str(path), line, column)
            if key in seen:
                continue
            seen.add(key)

            detail = f"Line {line}, column {column}"
            if mapped_from_preview:
                detail += f" — generated preview line {reported_line}"
            file_node.add_child(
                LatexDiagnosticNode(
                    "Compiler location",
                    detail,
                    "error",
                    source_path=path,
                    line=line,
                    column=column,
                )
            )
            matched = True
        return matched

    def _mark_missing_file_error(self, message: str) -> bool:
        match = self._FILE_NOT_FOUND_PATTERN.search(message)
        if match is None:
            return False
        target = match.group("target").strip()
        for (_path, _command, raw_target), node in self._edge_nodes.items():
            if raw_target == target or Path(raw_target).name == Path(target).name:
                if node.kind in {"missing", "error"}:
                    node.mark_error(f"LaTeX reports that `{target}` was not found.")
                    return True
        return False

    def _append_compiler_output(self, root: LatexDiagnosticNode, message: str) -> None:
        output = root.add_child(
            LatexDiagnosticNode(
                "Compiler output",
                "Useful lines reported by LaTeX",
                "compiler",
            )
        )
        for line in (value.strip() for value in message.splitlines()):
            if not line:
                continue
            output.add_child(
                LatexDiagnosticNode(
                    line,
                    "",
                    "error" if self._looks_like_error(line) else "info",
                )
            )

    def _edge_detail(self, target: Path | None, candidate: Path | None) -> str:
        if target is not None:
            return f"Resolved → {self._relative_display(target)}"
        return f"Not found → {self._display_path(candidate)}"

    def _relative_display(self, path: str | Path) -> str:
        resolved = Path(path).expanduser().resolve(strict=False)
        root = self._resolver.default_path
        if root is not None:
            try:
                relative = resolved.relative_to(root)
                return f"/{relative.as_posix()}"
            except ValueError:
                pass
        return resolved.as_posix()

    @staticmethod
    def _display_path(path: str | Path | None) -> str:
        if path is None:
            return "Not configured"
        return Path(path).expanduser().resolve(strict=False).as_posix()

    @staticmethod
    def _read_text(path: Path) -> str | None:
        for encoding in ("utf-8", "latin-1"):
            try:
                return path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
            except OSError:
                return None
        return None

    @staticmethod
    def _is_preview_temporary_path(path: Path) -> bool:
        normalized = path.as_posix()
        return "/tmp/nd_mind_mirror_" in normalized and path.name == "preview.tex"

    @staticmethod
    def _looks_like_error(line: str) -> bool:
        lowered = line.casefold()
        return (
            line.startswith("!")
            or "latex error" in lowered
            or "fatal error" in lowered
            or "could not resolve" in lowered
            or "not found" in lowered
        )

    @staticmethod
    def _primary_message(message: str) -> str:
        lines = [line.strip() for line in message.splitlines() if line.strip()]
        for line in lines:
            lowered = line.casefold()
            if line.startswith("!") or "latex error" in lowered:
                return line.lstrip("! ")
        for line in lines:
            if "could not resolve" in line.casefold():
                return line
        return lines[0] if lines else "LaTeX compilation failed."
