from pathlib import Path
import shutil
import tempfile

from PySide6.QtCore import (
    QProcess,
    QProcessEnvironment,
    QTimer,
)

from nd_mind_mirror.core.latex.input.recursive.recursive_input_resolver import (
    RecursiveInputResolver,
)
from nd_mind_mirror.core.render.base.renderer import Renderer
from nd_mind_mirror.core.render.latex.latex_preview_source_builder import (
    LatexPreviewSourceBuilder,
)


class LatexRenderer(Renderer):
    def __init__(
        self,
        template_path: str | Path,
        beamer_template_path: str | Path | None = None,
        shell_escape: bool = True,
        debounce_ms: int = 220,
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
        self._publish_counter = 0
        self._published_pdf_paths: list[Path] = []
        self._shell_escape = bool(shell_escape)
        self._phase = ""
        self._compile_output: list[str] = []
        self._last_process_output = ""
        self._process_environment = (
            QProcessEnvironment.systemEnvironment()
        )
        self._working_directory = Path.cwd()
        self._latex_executable = ""
        self._suppress_finished = False
        self._cache_source_path: Path | None = None

        self._input_resolver = RecursiveInputResolver()
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
        self._timer.setInterval(max(int(debounce_ms), 50))
        self._timer.timeout.connect(
            self._compile_pending_source
        )

    def apply_settings(
        self,
        template_path: str | Path,
        shell_escape: bool,
        debounce_ms: int | None = None,
        beamer_template_path: str | Path | None = None,
    ) -> None:
        self._preview_source_builder.set_template_path(
            template_path
        )
        self._preview_source_builder.set_beamer_template_path(
            beamer_template_path
        )
        self._shell_escape = bool(shell_escape)
        if debounce_ms is not None:
            self._timer.setInterval(
                max(int(debounce_ms), 50)
            )

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
            self._compile_pending_source()
            return

        self._timer.start()

    def _compile_pending_source(self) -> None:
        executable = shutil.which("lualatex")

        if executable is None:
            self.failed.emit(
                "lualatex was not found on PATH."
            )
            return

        self._stop_running_process()

        source = self._pending_source
        source_path = self._pending_source_path
        self._active_generation = self._pending_generation

        expanded = self._input_resolver.resolve(
            source,
            source_path,
        )

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
            return

        if exit_code != 0:
            self._emit_compile_failure()
            return

        if self._phase == "latex1":
            # Publish the first successful PDF immediately. This restores the
            # genuinely live feeling of the original preview. Bibliography and
            # cross-reference cleanup can continue afterward and republish a
            # refined PDF without blocking the first visible update.
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

        self.rendered.emit(str(published_pdf))
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
