from pathlib import Path
import re
import shutil
import tempfile

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


class LatexRenderer(Renderer):
    source_position_mapped = Signal(int, float, float)
    dependencies_changed = Signal(object)

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

        self._temp_dir = Path(
            tempfile.mkdtemp(prefix="nd_mind_mirror_")
        )
        self._tex_path = self._temp_dir / "preview.tex"
        self._pdf_path = self._temp_dir / "preview.pdf"
        self._pending_source = ""
        self._pending_source_path: Path | None = None
        self._latest_requested_generation = 0
        self._pending_generation = 0
        self._active_generation = 0
        self._last_published_generation = 0
        self._publish_counter = 0
        self._published_pdf_paths: list[Path] = []
        self._shell_escape = bool(shell_escape)
        self._phase = ""
        self._bibliography_ran_for_generation = False
        self._compile_output: list[str] = []
        self._last_process_output = ""
        self._process_environment = (
            QProcessEnvironment.systemEnvironment()
        )
        self._working_directory = Path.cwd()
        self._latex_executable = ""
        self._suppress_finished = False
        self._cache_source_path: Path | None = None
        self._current_source_text = ""
        self._current_prepared_text = ""
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
        self._preview_source_builder = (
            LatexPreviewSourceBuilder(
                template_path,
                beamer_template_path=beamer_template_path,
            )
        )

        self._process = QProcess(self)
        self._process.finished.connect(
            self._on_process_finished
        )

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(self._normal_debounce_ms)
        self._timer.timeout.connect(
            self._compile_pending_source
        )

        self._sync_process = QProcess(self)
        self._sync_process.finished.connect(
            self._on_sync_process_finished
        )
        self._sync_timer = QTimer(self)
        self._sync_timer.setSingleShot(True)
        self._sync_timer.setInterval(
            max(int(cursor_sync_debounce_ms), 30)
        )
        self._sync_timer.timeout.connect(
            self._map_pending_source_position
        )

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
        self._preview_source_builder.set_template_path(
            template_path
        )
        self._preview_source_builder.set_beamer_template_path(
            beamer_template_path
        )
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
            self._cursor_sync_enabled = bool(
                cursor_sync_enabled
            )
            if not self._cursor_sync_enabled:
                self._sync_timer.stop()
        if cursor_sync_debounce_ms is not None:
            self._sync_timer.setInterval(
                max(int(cursor_sync_debounce_ms), 30)
            )

    def request_source_position(
        self,
        source_path: str | Path,
        line: int,
        column: int,
    ) -> None:
        if not self._cursor_sync_enabled:
            return

        self._pending_sync_source_path = Path(
            source_path
        ).expanduser().resolve()
        self._pending_sync_line = max(int(line), 1)
        self._pending_sync_column = max(int(column), 1)
        # Never map a cursor position against a stale SyncTeX/PDF while a
        # newer source generation is queued or compiling. That race was a
        # major cause of the preview jumping to unrelated locations while
        # typing. The latest cursor position is retained and mapped as soon as
        # the matching PDF generation is published.
        if self._preview_is_current_for_sync():
            self._sync_timer.start()

    def render(
        self,
        source: str,
        source_path: str | Path | None = None,
        immediate: bool = False,
    ) -> None:
        self._latest_requested_generation += 1
        self._pending_generation = self._latest_requested_generation
        self._pending_source = source

        if source_path is None:
            self._pending_source_path = self._source_path
        else:
            self._pending_source_path = Path(
                source_path
            ).expanduser().resolve()
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

    def _compile_pending_source(self) -> None:
        # Live edits are coalesced while LuaLaTeX is already working.  Killing
        # and relaunching an 80-page document every few hundred milliseconds
        # causes severe CPU churn and is the main source of periodic editor
        # slowdowns.  The finished handler immediately starts only the newest
        # queued generation.
        if (
            self._process.state()
            != QProcess.ProcessState.NotRunning
        ):
            return

        executable = shutil.which("lualatex")

        if executable is None:
            self.failed.emit(
                "lualatex was not found on PATH."
            )
            return

        source = self._pending_source
        source_path = self._pending_source_path
        self._active_generation = self._pending_generation

        expanded = self._input_resolver.resolve(
            source,
            source_path,
        )
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
            prepared = self._preview_source_builder.build(
                source=expanded,
                source_path=source_path,
                title_source=source,
            )
        except (OSError, ValueError) as exc:
            if self._is_current_generation():
                self.failed.emit(str(exc))
            return

        # Keep AUX/BBl data while repeatedly editing the same file. This lets
        # the first live pass reuse already-resolved citations and references.
        # A tab/file switch gets a clean auxiliary state so one document cannot
        # leak labels or bibliography data into another.
        if source_path != self._cache_source_path:
            self._clean_previous_outputs(keep_auxiliary=False)
            self._cache_source_path = source_path
        else:
            self._clean_previous_outputs(keep_auxiliary=True)

        # Keep the original editor source and the generated preview source
        # together. SyncTeX line mapping depends on both; without these
        # snapshots cursor/scroll requests have no source lines to map.
        self._current_source_text = source
        self._current_prepared_text = prepared

        try:
            self._tex_path.write_text(
                prepared,
                encoding="utf-8",
            )
        except OSError as exc:
            if self._is_current_generation():
                self.failed.emit(str(exc))
            return

        self._working_directory = (
            source_path.parent
            if source_path is not None
            else Path.cwd()
        )
        self._process_environment = (
            self._build_process_environment(
                self._working_directory
            )
        )
        self._latex_executable = executable
        self._compile_output = []
        self._last_process_output = ""
        self._bibliography_ran_for_generation = False
        self._start_lualatex("latex1")

    def _build_process_environment(
        self,
        working_directory: Path,
    ) -> QProcessEnvironment:
        environment = QProcessEnvironment.systemEnvironment()
        tex_paths = [str(working_directory)]

        project_root = self._input_resolver.project_root
        if project_root is not None:
            tex_paths.append(f"{project_root}//")

        for ancestor in list(working_directory.parents)[:5]:
            tex_paths.append(str(ancestor))

        existing_texinputs = environment.value(
            "TEXINPUTS",
            "",
        )

        combined = ":".join(tex_paths)
        if existing_texinputs:
            combined += ":" + existing_texinputs
        else:
            combined += ":"

        environment.insert(
            "TEXINPUTS",
            combined,
        )
        return environment

    def _start_lualatex(
        self,
        phase: str,
    ) -> None:
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
                f"-output-directory={self._temp_dir}",
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
        bcf_path = self._temp_dir / "preview.bcf"
        aux_path = self._temp_dir / "preview.aux"
        bbl_path = self._temp_dir / "preview.bbl"
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
                working_directory=self._temp_dir,
            )
            return "started"

        aux_text = ""
        try:
            aux_text = aux_path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            pass

        has_bibdata = "\\bibdata" in aux_text
        has_citations = (
            "\\citation" in aux_text
            or "\\nocite" in aux_text
        )

        if not has_bibdata or not has_citations:
            return "none"

        needs_bibtex = (
            not bbl_path.is_file()
            or "undefined citations" in output_lower
            or "citation" in output_lower and "undefined" in output_lower
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
            working_directory=self._temp_dir,
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
        self._process.setProcessEnvironment(
            self._process_environment
        )
        self._process.setWorkingDirectory(
            str(working_directory)
        )
        self._process.setProgram(program)
        self._process.setArguments(arguments)
        self._process.start()

    def _on_process_finished(
        self,
        exit_code: int,
        exit_status,
    ) -> None:
        if self._suppress_finished:
            return

        stdout = bytes(
            self._process.readAllStandardOutput()
        ).decode(
            "utf-8",
            errors="replace",
        )
        stderr = bytes(
            self._process.readAllStandardError()
        ).decode(
            "utf-8",
            errors="replace",
        )
        output = (stdout + "\n" + stderr).strip()
        self._last_process_output = output
        if output:
            self._compile_output.append(output)

        if not self._is_current_generation():
            QTimer.singleShot(0, self._compile_pending_source)
            return

        if exit_code != 0:
            self._emit_compile_failure()
            return

        if self._phase == "latex1":
            # Resolve bibliography before publishing a newly built PDF when
            # BibTeX/Biber is actually required. Publishing latex1 first can
            # leave a visible `?` citation even though the bibliography itself
            # already appears later in the document. For documents that do not
            # need a bibliography tool, keep the original fast first-pass
            # publication behavior.
            bibliography_status = self._start_bibliography_tool()
            if bibliography_status == "started":
                return
            if bibliography_status == "missing":
                return

            if not self._publish_current_pdf():
                self._emit_compile_failure()
                return

            if self._needs_latex_rerun(output):
                self._start_lualatex("latex2")
            return

        if self._phase in {"bibtex", "biber"}:
            self._start_lualatex("latex2")
            return

        if self._phase == "latex2":
            # A bibliography build needs the canonical two LaTeX passes after
            # BibTeX/Biber. The first pass reads preview.bbl; the second settles
            # citation/reference state. Do not stop early merely because the
            # log omitted a generic rerun warning.
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

        published_pdf = self._publish_pdf(
            self._active_generation
        )
        if published_pdf is None:
            return False

        self._last_published_generation = self._active_generation
        self.rendered.emit(str(published_pdf))
        if self._cursor_sync_enabled:
            self._sync_timer.start()
        return True

    def _publish_pdf(
        self,
        generation: int,
    ) -> Path | None:
        self._publish_counter += 1
        destination = (
            self._temp_dir
            / (
                f"preview_render_{generation:08d}_"
                f"{self._publish_counter:08d}.pdf"
            )
        )

        try:
            shutil.copy2(
                self._pdf_path,
                destination,
            )
        except OSError as exc:
            self._compile_output.append(
                f"Could not publish rendered PDF: {exc}"
            )
            return None

        self._published_pdf_paths.append(destination)
        self._prune_published_pdfs()
        return destination

    def _prune_published_pdfs(self) -> None:
        while len(self._published_pdf_paths) > 8:
            stale = self._published_pdf_paths.pop(0)
            try:
                stale.unlink()
            except OSError:
                pass

    def _preview_is_current_for_sync(self) -> bool:
        return (
            self._last_published_generation == self._latest_requested_generation
            and not self._timer.isActive()
            and self._process.state() == QProcess.ProcessState.NotRunning
        )

    def _map_pending_source_position(self) -> None:
        if not self._cursor_sync_enabled:
            return
        if not self._preview_is_current_for_sync():
            return

        source_path = self._pending_sync_source_path
        if source_path is None or source_path != self._cache_source_path:
            return

        if not self._pdf_path.is_file():
            return

        synctex_path = self._temp_dir / "preview.synctex.gz"
        if not synctex_path.is_file():
            return

        executable = shutil.which("synctex")
        if executable is None:
            return

        preview_line = self._preview_line_for_source_line(
            self._pending_sync_line
        )
        if preview_line is None:
            return

        if (
            self._sync_process.state()
            != QProcess.ProcessState.NotRunning
        ):
            self._sync_process.kill()
            self._sync_process.waitForFinished(250)

        self._sync_process.setWorkingDirectory(
            str(self._temp_dir)
        )
        self._sync_process.setProgram(executable)
        self._sync_process.setArguments(
            [
                "view",
                "-i",
                (
                    f"{preview_line}:"
                    f"{self._pending_sync_column}:"
                    f"{self._tex_path}"
                ),
                "-o",
                str(self._pdf_path),
            ]
        )
        self._sync_process.start()

    def _on_sync_process_finished(
        self,
        exit_code: int,
        exit_status,
    ) -> None:
        if exit_code != 0:
            return

        output = bytes(
            self._sync_process.readAllStandardOutput()
        ).decode(
            "utf-8",
            errors="replace",
        )

        page_match = re.search(r"(?m)^Page:(\d+)", output)
        x_match = re.search(
            r"(?m)^x:([-+]?\d+(?:\.\d+)?)",
            output,
        )
        y_match = re.search(
            r"(?m)^y:([-+]?\d+(?:\.\d+)?)",
            output,
        )
        if page_match is None or x_match is None or y_match is None:
            return

        page = max(int(page_match.group(1)) - 1, 0)
        x = float(x_match.group(1))
        y = float(y_match.group(1))
        self.source_position_mapped.emit(page, x, y)

    def _preview_line_for_source_line(
        self,
        source_line: int,
    ) -> int | None:
        source_lines = self._current_source_text.splitlines()
        prepared_lines = self._current_prepared_text.splitlines()
        if not source_lines or not prepared_lines:
            return None

        source_index = max(
            0,
            min(int(source_line) - 1, len(source_lines) - 1),
        )

        # Cursor lines are often blank or syntactically repetitive. Search a
        # small neighborhood for the nearest non-empty source line, then map
        # that exact line into the generated preview source. This keeps cursor
        # sync cheap enough to run while editing even for large documents.
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

        # Last-resort approximation if the current source line was transformed
        # by recursive input expansion. It is intentionally conservative; a
        # later cursor move on a normal prose/command line will refine it.
        ratio = source_index / max(len(source_lines) - 1, 1)
        return max(
            1,
            min(
                int(round(ratio * (len(prepared_lines) - 1))) + 1,
                len(prepared_lines),
            ),
        )

    def _emit_compile_failure(self) -> None:
        output = "\n".join(
            self._compile_output
        ).strip()
        message = self._extract_useful_error(
            output
        )

        unresolved = self._input_resolver.unresolved
        if unresolved:
            message += (
                "\n\nnd_mind_mirror unresolved inputs:\n"
                + "\n".join(unresolved)
            )

        self.failed.emit(message)

    def _is_current_generation(self) -> bool:
        return (
            self._active_generation
            == self._latest_requested_generation
        )

    def _stop_running_process(self) -> None:
        if (
            self._process.state()
            == QProcess.ProcessState.NotRunning
        ):
            return

        self._suppress_finished = True
        self._process.kill()
        self._process.waitForFinished(1000)
        self._suppress_finished = False

    def _clean_previous_outputs(
        self,
        keep_auxiliary: bool,
    ) -> None:
        keep_suffixes = {
            ".aux",
            ".bbl",
            ".blg",
            ".toc",
            ".out",
            ".nav",
            ".snm",
        }

        for path in self._temp_dir.glob("preview.*"):
            if path == self._tex_path:
                continue
            if keep_auxiliary and path.suffix in keep_suffixes:
                continue
            try:
                path.unlink()
            except OSError:
                pass

    def _extract_useful_error(
        self,
        output: str,
    ) -> str:
        if not output:
            return (
                "LaTeX compilation failed without "
                "diagnostic output."
            )

        lines = [
            line
            for line in output.splitlines()
            if line.strip()
        ]

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

        selected = (
            interesting[-24:]
            if interesting
            else lines[-30:]
        )

        return "\n".join(selected)
