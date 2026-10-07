from pathlib import Path
import re
import shutil

from PySide6.QtCore import (
    QProcess,
    QProcessEnvironment,
    QTimer,
    Signal,
)

from nd_mind_mirror.core.latex.input.recursive.recursive_input_resolver import (
    RecursiveInputResolver,
)
from nd_mind_mirror.core.render.base.renderer import Renderer
from nd_mind_mirror.graphic.core.dependency_resolver import GraphicDependencyResolver
from nd_mind_mirror.core.render.latex.latex_preview_source_builder import (
    LatexPreviewSourceBuilder,
)
from nd_mind_mirror.core.render.latex.latex_build_workspace import (
    LatexBuildWorkspace,
)


class LatexRenderer(Renderer):
    source_position_mapped = Signal(int, float, float)
    dependencies_changed = Signal(object)

    _PERSIAN_SCRIPT_PATTERN = re.compile(
        "[\u0600-\u06ff\u0750-\u077f\u0870-\u089f"
        "\u08a0-\u08ff\ufb50-\ufdff\ufe70-\ufeff]"
    )
    _LUA_PACKAGE_PATTERN = re.compile(
        r"\\usepackage(?:\[[^\]]*\])?\{[^}]*"
        r"(?:fontspec|unicode-math|xepersian|polyglossia|luacode|luaotfload)"
        r"[^}]*\}",
        re.IGNORECASE,
    )
    _LUA_PREPARED_PATTERN = re.compile(
        r"\\(?:setmainfont|setsansfont|setmonofont|newfontfamily|setmathfont|usegdlibrary)\b"
        r"|graphdrawing",
        re.IGNORECASE,
    )
    _LUA_SOURCE_PATTERN = re.compile(
        r"\\(?:directlua|includegraphvizrel)\b",
        re.IGNORECASE,
    )
    _TIKZ_LIBRARY_LINE_PATTERN = re.compile(
        r"^(?P<indent>[ \t]*)\\usetikzlibrary\s*"
        r"\{(?P<items>[^}]*)\}(?P<tail>[ \t]*(?:%.*)?)$"
    )
    _GD_LIBRARY_LINE_PATTERN = re.compile(
        r"^(?P<indent>[ \t]*)\\usegdlibrary\s*"
        r"\{[^}]*\}(?P<tail>[ \t]*(?:%.*)?)$"
    )
    _GRAPH_DRAWING_USE_PATTERN = re.compile(
        r"\\graph\b"
        r"|\\pgfgd\b"
        r"|(?:layered|tree|spring|circular|force|random)\s+layout\b",
        re.IGNORECASE,
    )

    def __init__(
        self,
        template_path: str | Path,
        beamer_template_path: str | Path | None = None,
        shell_escape: bool = True,
        debounce_ms: int = 220,
        cursor_sync_enabled: bool = True,
        cursor_sync_debounce_ms: int = 120,
        large_document_threshold_chars: int = 120000,
        large_document_debounce_ms: int = 650,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._build_workspace = LatexBuildWorkspace()
        # Keep _temp_dir as the renderer-wide workspace root for compatibility
        # with cache users in the derived renderer. Compiler output itself lives
        # in generation-specific directories owned by LatexBuildWorkspace.
        self._temp_dir = self._build_workspace.root
        self._build_dir = self._temp_dir
        self._tex_path = self._temp_dir / "preview.tex"
        self._pdf_path = self._temp_dir / "preview.pdf"
        self._enabled = True
        self._pending_source = ""
        self._pending_source_path: Path | None = None
        self._latest_requested_generation = 0
        self._pending_generation = 0
        self._active_generation = 0
        self._last_published_generation = 0
        self._publish_counter = 0
        self._shell_escape = bool(shell_escape)
        self._phase = ""
        self._bibliography_ran_for_generation = False
        self._compile_output: list[str] = []
        self._last_process_output = ""
        self._process_environment = QProcessEnvironment.systemEnvironment()
        self._working_directory = Path.cwd()
        self._latex_executable = ""
        self._latex_engine = ""
        self._fast_engine_fallback_attempted = False
        self._suppress_finished = False
        self._cache_source_path: Path | None = None
        self._current_source_text = ""
        self._current_prepared_text = ""
        self._published_tex_by_pdf: dict[Path, str] = {}
        self._cursor_sync_enabled = bool(cursor_sync_enabled)
        self._pending_sync_source_path: Path | None = None
        self._pending_sync_line = 1
        self._pending_sync_column = 1
        self._normal_debounce_ms = max(int(debounce_ms), 50)
        self._large_document_threshold_chars = max(
            int(large_document_threshold_chars),
            10000,
        )
        self._large_document_debounce_ms = max(
            int(large_document_debounce_ms),
            self._normal_debounce_ms,
        )

        self._input_resolver = RecursiveInputResolver()
        self._graphic_dependency_resolver = GraphicDependencyResolver()
        self._preview_source_builder = LatexPreviewSourceBuilder(
            template_path,
            beamer_template_path=beamer_template_path,
        )

        self._process = QProcess(self)
        self._process.finished.connect(self._on_process_finished)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(self._normal_debounce_ms)
        self._timer.timeout.connect(self._compile_pending_source)

        self._sync_process = QProcess(self)
        self._sync_process.finished.connect(self._on_sync_process_finished)
        self._sync_timer = QTimer(self)
        self._sync_timer.setSingleShot(True)
        self._sync_timer.setInterval(max(int(cursor_sync_debounce_ms), 30))
        self._sync_timer.timeout.connect(self._map_pending_source_position)

        self._compile_watchdog = QTimer(self)
        self._compile_watchdog.setSingleShot(True)
        self._compile_watchdog.setInterval(60_000)
        self._compile_watchdog.timeout.connect(self._on_compile_timeout)

    def apply_settings(
        self,
        template_path: str | Path,
        shell_escape: bool,
        debounce_ms: int | None = None,
        beamer_template_path: str | Path | None = None,
        cursor_sync_enabled: bool | None = None,
        cursor_sync_debounce_ms: int | None = None,
        large_document_threshold_chars: int | None = None,
        large_document_debounce_ms: int | None = None,
    ) -> None:
        self._preview_source_builder.set_template_path(template_path)
        self._preview_source_builder.set_beamer_template_path(beamer_template_path)
        self._shell_escape = bool(shell_escape)
        if debounce_ms is not None:
            self._normal_debounce_ms = max(int(debounce_ms), 50)
            self._timer.setInterval(self._normal_debounce_ms)
        if large_document_threshold_chars is not None:
            self._large_document_threshold_chars = max(
                int(large_document_threshold_chars),
                10000,
            )
        if large_document_debounce_ms is not None:
            self._large_document_debounce_ms = max(
                int(large_document_debounce_ms),
                self._normal_debounce_ms,
            )
        if cursor_sync_enabled is not None:
            self._cursor_sync_enabled = bool(cursor_sync_enabled)
            if not self._cursor_sync_enabled:
                self._sync_timer.stop()
        if cursor_sync_debounce_ms is not None:
            self._sync_timer.setInterval(max(int(cursor_sync_debounce_ms), 30))

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        if self._enabled:
            return
        self._timer.stop()
        self._sync_timer.stop()
        self._stop_running_process()
        if self._sync_process.state() != QProcess.ProcessState.NotRunning:
            self._sync_process.kill()
            self._sync_process.waitForFinished(250)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def request_source_position(
        self,
        source_path: str | Path,
        line: int,
        column: int,
    ) -> None:
        if not self._enabled or not self._cursor_sync_enabled:
            return
        self._pending_sync_source_path = Path(source_path).expanduser().resolve()
        self._pending_sync_line = max(int(line), 1)
        self._pending_sync_column = max(int(column), 1)
        if self._preview_is_current_for_sync():
            self._sync_timer.start()

    def render(
        self,
        source: str,
        source_path: str | Path | None = None,
        immediate: bool = False,
    ) -> None:
        if not self._enabled:
            return
        self._latest_requested_generation += 1
        self._pending_generation = self._latest_requested_generation
        self._pending_source = source
        if source_path is None:
            self._pending_source_path = self._source_path
        else:
            self._pending_source_path = Path(source_path).expanduser().resolve()
            self._source_path = self._pending_source_path

        if immediate:
            self._timer.stop()
            self._stop_running_process()
            self._compile_pending_source()
            return

        debounce = (
            self._large_document_debounce_ms
            if len(source) >= self._large_document_threshold_chars
            else self._normal_debounce_ms
        )
        self._timer.setInterval(debounce)
        self._timer.start()

    def prepare_preview_source(
        self,
        source: str,
        source_path: str | Path | None = None,
    ) -> str:
        """Build the exact LaTeX text that Preview would compile."""
        resolved_source_path = (
            self._source_path
            if source_path is None
            else Path(source_path).expanduser().resolve()
        )
        expanded = self._input_resolver.resolve(
            source,
            resolved_source_path,
        )
        return self._prepare_preview_source(
            source=source,
            source_path=resolved_source_path,
            expanded_source=expanded,
        )

    def _prepare_preview_source(
        self,
        *,
        source: str,
        source_path: Path | None,
        expanded_source: str,
    ) -> str:
        prepared = self._preview_source_builder.build(
            source=expanded_source,
            source_path=source_path,
            title_source=source,
        )
        return self._optimize_preview_for_fast_engine(
            prepared,
            expanded_source,
        )

    def prepared_source_for_pdf(
        self,
        pdf_path: str | Path,
    ) -> str | None:
        """Return the prepared LaTeX that produced a published Preview PDF."""
        try:
            resolved = Path(pdf_path).expanduser().resolve()
        except (OSError, TypeError, ValueError):
            return None
        return self._published_tex_by_pdf.get(resolved)

    def _remember_published_tex(
        self,
        pdf_path: str | Path,
        prepared_source: str | None = None,
    ) -> None:
        """Associate a rendered PDF with the exact prepared LaTeX that produced it."""
        try:
            resolved = Path(pdf_path).expanduser().resolve()
        except (OSError, TypeError, ValueError):
            return
        source = (
            self._current_prepared_text
            if prepared_source is None
            else str(prepared_source)
        )
        if source:
            self._published_tex_by_pdf[resolved] = source

    def _compile_pending_source(self) -> None:
        if self._process.state() != QProcess.ProcessState.NotRunning:
            return

        source = self._pending_source
        source_path = self._pending_source_path
        self._active_generation = self._pending_generation

        expanded = self._input_resolver.resolve(source, source_path)
        graphic_dependencies = self._graphic_dependency_resolver.collect(
            source,
            source_path,
            self._input_resolver.resolved_paths,
        )
        dependency_paths = list(self._input_resolver.resolved_paths)
        for dependency in graphic_dependencies:
            if dependency not in dependency_paths:
                dependency_paths.append(dependency)
        self.dependencies_changed.emit([str(path) for path in dependency_paths])

        try:
            prepared = self._prepare_preview_source(
                source=source,
                source_path=source_path,
                expanded_source=expanded,
            )
        except (OSError, ValueError) as exc:
            if self._is_current_generation():
                self.failed.emit(str(exc))
            return

        executable, engine = self._select_latex_engine(source, prepared)
        if executable is None:
            if self._is_current_generation():
                self.failed.emit(
                    "No usable LaTeX engine was found on PATH "
                    "(tried pdflatex and lualatex)."
                )
            return

        try:
            build = self._build_workspace.start_generation(
                generation=self._active_generation,
                source_path=source_path,
            )
        except OSError as exc:
            if self._is_current_generation():
                self.failed.emit(f"Could not prepare LaTeX build workspace: {exc}")
            return
        self._build_dir = build.directory
        self._tex_path = build.tex_path
        self._pdf_path = build.pdf_path
        self._cache_source_path = source_path

        self._current_source_text = source
        self._current_prepared_text = prepared

        try:
            self._tex_path.write_text(prepared, encoding="utf-8")
        except OSError as exc:
            if self._is_current_generation():
                self.failed.emit(str(exc))
            return

        self._working_directory = (
            source_path.parent if source_path is not None else Path.cwd()
        )
        self._process_environment = self._build_process_environment(
            self._working_directory
        )
        self._latex_executable = executable
        self._latex_engine = engine
        self._fast_engine_fallback_attempted = False
        self._compile_output = []
        self._last_process_output = ""
        self._bibliography_ran_for_generation = False
        self._start_lualatex("latex1")

    def _optimize_preview_for_fast_engine(
        self,
        prepared: str,
        expanded_source: str,
    ) -> str:
        """Omit unused PGF graph-drawing libraries from the temporary preview."""
        if self._GRAPH_DRAWING_USE_PATTERN.search(expanded_source):
            return prepared

        optimized: list[str] = []
        for line in prepared.splitlines(keepends=True):
            body = line.rstrip("\r\n")
            newline = line[len(body):]

            tikz_match = self._TIKZ_LIBRARY_LINE_PATTERN.match(body)
            if tikz_match is not None:
                items = [
                    item.strip()
                    for item in tikz_match.group("items").split(",")
                    if item.strip()
                ]
                filtered = [
                    item
                    for item in items
                    if item.casefold() != "graphdrawing"
                ]
                if len(filtered) != len(items):
                    indent = tikz_match.group("indent")
                    tail = tikz_match.group("tail") or ""
                    if filtered:
                        body = (
                            indent
                            + "\\usetikzlibrary{"
                            + ",".join(filtered)
                            + "}"
                            + tail
                        )
                    else:
                        body = (
                            indent
                            + "% nd_mind_mirror preview: "
                            + "unused graphdrawing library omitted"
                        )
                    optimized.append(body + newline)
                    continue

            gd_match = self._GD_LIBRARY_LINE_PATTERN.match(body)
            if gd_match is not None:
                optimized.append(
                    gd_match.group("indent")
                    + "% nd_mind_mirror preview: "
                    + "unused graph drawing library omitted"
                    + newline
                )
                continue

            optimized.append(line)

        return "".join(optimized)

    def _select_latex_engine(
        self,
        source: str,
        prepared: str,
    ) -> tuple[str | None, str]:
        requires_lua = bool(
            self._PERSIAN_SCRIPT_PATTERN.search(prepared)
            or self._LUA_PACKAGE_PATTERN.search(prepared)
            or self._LUA_PREPARED_PATTERN.search(prepared)
            or self._LUA_SOURCE_PATTERN.search(source)
        )

        if not requires_lua:
            executable = shutil.which("pdflatex")
            if executable is not None:
                return executable, "pdflatex"

        executable = shutil.which("lualatex")
        if executable is not None:
            return executable, "lualatex"

        if requires_lua:
            return None, "lualatex"

        executable = shutil.which("pdflatex")
        return executable, "pdflatex" if executable else ""

    def _build_process_environment(
        self,
        working_directory: Path,
    ) -> QProcessEnvironment:
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("LANG", "C.UTF-8")
        environment.insert("LC_ALL", "C.UTF-8")
        # Keep TeX lookup local and deterministic. A recursive project-root
        # entry (``project_root//``) makes kpathsea walk the entire Dropbox
        # repository for package and asset lookups on every live compile.
        # Recursive ``\\input``/``\\include`` files are already expanded by
        # RecursiveInputResolver, while ordinary relative assets resolve from
        # the source document directory.
        environment.insert("TEXINPUTS", f"{working_directory}:")
        return environment

    def _start_lualatex(self, phase: str) -> None:
        arguments = [
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-file-line-error",
            "-synctex=1",
        ]
        if self._shell_escape:
            arguments.append("-shell-escape")
        arguments.extend(
            [
                f"-output-directory={self._build_dir}",
                str(self._tex_path),
            ]
        )
        self._start_process(
            phase=phase,
            program=self._latex_executable,
            arguments=arguments,
            working_directory=self._working_directory,
        )

    def _start_bibliography_tool(self) -> str:
        bcf_path = self._build_dir / "preview.bcf"
        aux_path = self._build_dir / "preview.aux"
        bbl_path = self._build_dir / "preview.bbl"
        output_lower = self._last_process_output.lower()

        if bcf_path.is_file():
            needs_biber = (
                not bbl_path.is_file()
                or "rerun biber" in output_lower
                or "run biber" in output_lower
                or "undefined" in output_lower
            )
            if not needs_biber:
                return "none"
            executable = shutil.which("biber")
            if executable is None:
                self.failed.emit(
                    "This preview requires biber, but biber was not found on PATH."
                )
                return "missing"
            self._bibliography_ran_for_generation = True
            self._start_process(
                phase="biber",
                program=executable,
                arguments=["preview"],
                working_directory=self._build_dir,
            )
            return "started"

        try:
            aux_text = aux_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            aux_text = ""

        has_bibdata = "\\bibdata" in aux_text
        has_citations = "\\citation" in aux_text or "\\nocite" in aux_text
        if not has_bibdata or not has_citations:
            return "none"

        needs_bibtex = (
            not bbl_path.is_file()
            or "undefined citations" in output_lower
            or ("citation" in output_lower and "undefined" in output_lower)
            or "rerun bibtex" in output_lower
            or "run bibtex" in output_lower
        )
        if not needs_bibtex:
            return "none"

        executable = (
            shutil.which("bibtex")
            or shutil.which("bibtexu")
            or shutil.which("bibtex8")
        )
        if executable is None:
            self.failed.emit(
                "This preview contains citations and a bibliography, "
                "but no BibTeX executable (bibtex, bibtexu, or bibtex8) "
                "was found on PATH."
            )
            return "missing"

        self._bibliography_ran_for_generation = True
        self._start_process(
            phase="bibtex",
            program=executable,
            arguments=["preview"],
            working_directory=self._build_dir,
        )
        return "started"

    def _start_process(
        self,
        phase: str,
        program: str,
        arguments: list[str],
        working_directory: Path,
    ) -> None:
        self._phase = phase
        self._process.setProcessEnvironment(self._process_environment)
        self._process.setWorkingDirectory(str(working_directory))
        self._process.setProgram(program)
        self._process.setArguments(arguments)
        self._process.start()
        self._compile_watchdog.start()

    def _on_process_finished(self, exit_code: int, exit_status) -> None:
        self._compile_watchdog.stop()
        if self._suppress_finished:
            return

        stdout = bytes(self._process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        stderr = bytes(self._process.readAllStandardError()).decode(
            "utf-8", errors="replace"
        )
        output = (stdout + "\n" + stderr).strip()
        self._last_process_output = output
        if output:
            self._compile_output.append(output)

        if exit_code == 0:
            # Snapshot only subprocess output that completed normally. Future
            # generations seed from this immutable checkpoint, never from the
            # active/canceled build directory itself.
            self._build_workspace.checkpoint_auxiliary()

        if not self._is_current_generation():
            QTimer.singleShot(0, self._compile_pending_source)
            return

        if exit_code != 0:
            if self._retry_with_lualatex_after_fast_engine_failure():
                return
            self._emit_compile_failure()
            return

        if self._phase == "latex1":
            # ND_FAST_FIRST_PASS_PUBLISH
            # Publish the first successful PDF immediately. Bibliography and
            # reference-settling passes continue only after the user already
            # has a visible preview.
            if not self._publish_current_pdf():
                self._emit_compile_failure()
                return

            bibliography_status = self._start_bibliography_tool()
            if bibliography_status == "started":
                return
            if bibliography_status == "missing":
                return

            if self._needs_latex_rerun(output):
                self._start_lualatex("latex2")
            return

        if self._phase in {"bibtex", "biber"}:
            self._start_lualatex("latex2")
            return

        if self._phase == "latex2":
            if self._bibliography_ran_for_generation:
                self._start_lualatex("latex3")
                return
            if not self._publish_current_pdf():
                self._emit_compile_failure()
                return
            if self._needs_latex_rerun(output):
                self._start_lualatex("latex3")
            return

        if self._phase == "latex3":
            if not self._publish_current_pdf():
                self._emit_compile_failure()
            return

        self._emit_compile_failure()

    def _retry_with_lualatex_after_fast_engine_failure(self) -> bool:
        if (
            not self._phase.startswith("latex")
            or self._latex_engine != "pdflatex"
            or self._fast_engine_fallback_attempted
        ):
            return False
        executable = shutil.which("lualatex")
        if executable is None:
            return False

        self._fast_engine_fallback_attempted = True
        self._latex_engine = "lualatex"
        self._latex_executable = executable
        self._compile_output = []
        self._last_process_output = ""
        self._build_workspace.reset_active_outputs(keep_tex=True)
        self._start_lualatex(self._phase)
        return True

    def _needs_latex_rerun(self, output: str) -> bool:
        lower = output.lower()
        return any(
            marker in lower
            for marker in (
                "rerun to get cross-references right",
                "label(s) may have changed",
                "rerunfilecheck warning: file",
                "please rerun latex",
            )
        )

    def _publish_current_pdf(self) -> bool:
        if not self._pdf_path.exists():
            return False
        published_pdf = self._publish_pdf(self._active_generation)
        if published_pdf is None:
            return False
        self._remember_published_tex(published_pdf)
        self._last_published_generation = self._active_generation
        self.rendered.emit(str(published_pdf))
        if self._cursor_sync_enabled:
            self._sync_timer.start()
        return True

    def _publish_pdf(self, generation: int) -> Path | None:
        self._publish_counter += 1
        destination = self._build_workspace.publish_pdf(
            generation=generation,
            sequence=self._publish_counter,
        )
        if destination is None:
            self._compile_output.append("Could not publish rendered PDF.")
        return destination

    def _preview_is_current_for_sync(self) -> bool:
        return (
            self._last_published_generation == self._latest_requested_generation
            and not self._timer.isActive()
            and self._process.state() == QProcess.ProcessState.NotRunning
        )

    def _map_pending_source_position(self) -> None:
        if not self._cursor_sync_enabled or not self._preview_is_current_for_sync():
            return
        source_path = self._pending_sync_source_path
        if source_path is None or source_path != self._cache_source_path:
            return
        if not self._pdf_path.is_file():
            return
        synctex_path = self._build_dir / "preview.synctex.gz"
        if not synctex_path.is_file():
            return
        executable = shutil.which("synctex")
        if executable is None:
            return
        preview_line = self._preview_line_for_source_line(self._pending_sync_line)
        if preview_line is None:
            return
        if self._sync_process.state() != QProcess.ProcessState.NotRunning:
            self._sync_process.kill()
            self._sync_process.waitForFinished(250)
        self._sync_process.setWorkingDirectory(str(self._build_dir))
        self._sync_process.setProgram(executable)
        self._sync_process.setArguments(
            [
                "view",
                "-i",
                f"{preview_line}:{self._pending_sync_column}:{self._tex_path}",
                "-o",
                str(self._pdf_path),
            ]
        )
        self._sync_process.start()

    def _on_sync_process_finished(self, exit_code: int, exit_status) -> None:
        if exit_code != 0:
            return
        output = bytes(self._sync_process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        page_match = re.search(r"(?m)^Page:(\d+)", output)
        x_match = re.search(r"(?m)^x:([-+]?\d+(?:\.\d+)?)", output)
        y_match = re.search(r"(?m)^y:([-+]?\d+(?:\.\d+)?)", output)
        if page_match is None or x_match is None or y_match is None:
            return
        page = max(int(page_match.group(1)) - 1, 0)
        self.source_position_mapped.emit(
            page,
            float(x_match.group(1)),
            float(y_match.group(1)),
        )

    def _preview_line_for_source_line(self, source_line: int) -> int | None:
        source_lines = self._current_source_text.splitlines()
        prepared_lines = self._current_prepared_text.splitlines()
        if not source_lines or not prepared_lines:
            return None

        source_index = max(0, min(int(source_line) - 1, len(source_lines) - 1))
        candidate_source_indices = [source_index]
        for distance in range(1, 9):
            candidate_source_indices.extend(
                [source_index - distance, source_index + distance]
            )

        best_rank: tuple[int, int, float, int] | None = None
        best_offset: int | None = None
        for nearby_index in candidate_source_indices:
            if nearby_index < 0 or nearby_index >= len(source_lines):
                continue
            target = source_lines[nearby_index]
            if not target.strip():
                continue
            for prepared_index, prepared_line in enumerate(prepared_lines):
                if prepared_line != target:
                    continue
                score = 0
                for delta in (-3, -2, -1, 1, 2, 3):
                    source_neighbor = nearby_index + delta
                    prepared_neighbor = prepared_index + delta
                    if (
                        0 <= source_neighbor < len(source_lines)
                        and 0 <= prepared_neighbor < len(prepared_lines)
                        and source_lines[source_neighbor]
                        == prepared_lines[prepared_neighbor]
                    ):
                        score += 1
                distance_penalty = abs(nearby_index - source_index)
                source_ratio = nearby_index / max(len(source_lines) - 1, 1)
                prepared_ratio = prepared_index / max(len(prepared_lines) - 1, 1)
                ratio_penalty = abs(source_ratio - prepared_ratio)
                rank = (
                    score,
                    -distance_penalty,
                    -ratio_penalty,
                    -prepared_index,
                )
                if best_rank is None or rank > best_rank:
                    best_rank = rank
                    best_offset = prepared_index - nearby_index
            if best_rank is not None and best_rank[0] >= 3:
                break

        if best_offset is not None:
            return max(source_index + best_offset + 1, 1)
        ratio = source_index / max(len(source_lines) - 1, 1)
        return max(
            1,
            min(
                int(round(ratio * (len(prepared_lines) - 1))) + 1,
                len(prepared_lines),
            ),
        )

    def _emit_compile_failure(self) -> None:
        output = "\n".join(self._compile_output).strip()
        message = self._extract_useful_error(output)
        unresolved = self._input_resolver.unresolved
        if unresolved:
            message += (
                "\n\nnd_mind_mirror unresolved inputs:\n"
                + "\n".join(unresolved)
            )
        self.failed.emit(message)

    def _is_current_generation(self) -> bool:
        return self._active_generation == self._latest_requested_generation

    def _on_compile_timeout(self) -> None:
        """Abort a stuck preview subprocess; its generation stays isolated."""
        if self._process.state() == QProcess.ProcessState.NotRunning:
            return

        phase = self._phase or "latex"
        self._compile_watchdog.stop()
        self._suppress_finished = True
        self._process.kill()
        self._process.waitForFinished(1000)
        self._suppress_finished = False

        if self._is_current_generation():
            self.failed.emit(f"Preview {phase} timed out after 60 seconds.")

        if self._pending_generation > self._active_generation:
            QTimer.singleShot(0, self._compile_pending_source)

    def _stop_running_process(self) -> None:
        if self._process.state() == QProcess.ProcessState.NotRunning:
            return
        self._compile_watchdog.stop()
        self._suppress_finished = True
        self._process.kill()
        self._process.waitForFinished(1000)
        self._suppress_finished = False

    def _extract_useful_error(self, output: str) -> str:
        if not output:
            return "LaTeX compilation failed without diagnostic output."
        lines = [line for line in output.splitlines() if line.strip()]
        interesting = [
            line
            for line in lines
            if line.startswith("!")
            or "preview.tex:" in line
            or "LaTeX Error" in line
            or "Undefined control sequence" in line
            or "Emergency stop" in line
            or "not found" in line
            or "Citation" in line
            or "Warning--" in line
        ]
        selected = interesting[-24:] if interesting else lines[-30:]
        return "\n".join(selected)
