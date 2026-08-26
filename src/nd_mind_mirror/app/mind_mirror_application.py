"""Create the Qt application, refresh the iPad transfer package, and launch the enhanced Mind Mirror window."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import shutil
import signal
import sys
import tempfile
import traceback
from typing import Callable

from PySide6.QtCore import QProcess, QTimer
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from nd_mind_mirror.graphic.ipad.package_builder import IpadPackageBuilder
from nd_mind_mirror.ui.icon.mind_mirror_icon import build_mind_mirror_icon
from nd_mind_mirror.ui.window.main.editor_interaction_enhancements import (
    EditorInteractionEnhancements,
)
from nd_mind_mirror.ui.window.main.persistent_editor_visuals import (
    PersistentEditorVisuals,
)
from nd_mind_mirror.ui.window.main.enhanced_main_window import EnhancedMainWindow
from nd_mind_mirror.ui.window.main.main_window import MainWindow
from nd_mind_mirror.ui.window.main.workspace_interaction_controller import (
    WorkspaceInteractionController,
)
from nd_mind_mirror.ui.window.main.navigator_stability_controller import (
    NavigatorStabilityController,
)
from nd_mind_mirror.ui.window.main.late_runtime_fixes import LateRuntimeFixes


_LOG_PATH = Path.home() / ".local" / "state" / "nd_mind_mirror_project" / "startup.log"


def _log(message: str) -> None:
    """Append one best-effort startup/lifetime diagnostic line to the application state log."""
    try:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _LOG_PATH.open("a", encoding="utf-8") as stream:
            stamp = datetime.now().isoformat(timespec="seconds")
            stream.write(f"[{stamp}] {message}\n")
    except OSError:
        pass


def _refresh_ipad_package() -> None:
    """Migrate the visible Swift package and rebuild nd_graphic.zip before Qt starts."""
    project_root = Path(__file__).resolve().parents[3]
    try:
        package = IpadPackageBuilder(project_root).refresh()
        if package is not None:
            _log(f"iPad transfer package ready: {package}")
    except Exception:
        _log("Could not refresh iPad transfer package:\n" + traceback.format_exc())


class _CanonicalPdfExportJob:
    """Compile the actual current LaTeX file without routing it through Preview transformations."""

    def __init__(
        self,
        window: MainWindow,
        source_path: Path,
        destination_path: Path,
    ) -> None:
        self._window = window
        self._source_path = source_path
        self._destination_path = destination_path
        self._temp_dir = Path(tempfile.mkdtemp(prefix="nd_mind_mirror_export_"))
        self._stem = source_path.stem
        self._phase = ""
        self._output: list[str] = []
        self._process = QProcess(window)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.finished.connect(self._on_finished)

    def start(self) -> None:
        executable = shutil.which("lualatex")
        if executable is None:
            self._fail("lualatex was not found on PATH.")
            return
        self._lualatex = executable
        self._start_lualatex("latex1")

    def _start_lualatex(self, phase: str) -> None:
        self._phase = phase
        arguments = [
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-file-line-error",
        ]
        if bool(getattr(self._window._app_settings, "preview_shell_escape", True)):
            arguments.append("-shell-escape")
        arguments.extend(
            [
                f"-output-directory={self._temp_dir}",
                str(self._source_path),
            ]
        )
        self._start_process(
            program=self._lualatex,
            arguments=arguments,
            working_directory=self._source_path.parent,
        )

    def _start_bibliography(self, tool: str) -> None:
        executable = shutil.which(tool)
        if executable is None:
            self._fail(f"{tool} is required by this document but was not found on PATH.")
            return
        self._phase = tool
        self._start_process(
            program=executable,
            arguments=[self._stem],
            working_directory=self._temp_dir,
        )

    def _start_process(
        self,
        program: str,
        arguments: list[str],
        working_directory: Path,
    ) -> None:
        try:
            environment = self._window._renderer._build_process_environment(
                self._source_path.parent
            )
            self._process.setProcessEnvironment(environment)
        except (AttributeError, RuntimeError):
            pass
        self._process.setWorkingDirectory(str(working_directory))
        self._process.setProgram(program)
        self._process.setArguments(arguments)
        self._process.start()

    def _bibliography_tool(self) -> str | None:
        bcf_path = self._temp_dir / f"{self._stem}.bcf"
        if bcf_path.is_file():
            return "biber"

        aux_path = self._temp_dir / f"{self._stem}.aux"
        try:
            aux_text = aux_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        if "\\bibdata" in aux_text and (
            "\\citation" in aux_text or "\\nocite" in aux_text
        ):
            return "bibtex"
        return None

    def _on_finished(self, exit_code: int, _exit_status) -> None:
        output = bytes(self._process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        if output:
            self._output.append(output)

        if exit_code != 0:
            detail = "\n".join(self._output)[-6000:]
            self._fail(detail or f"{self._phase} failed with exit code {exit_code}.")
            return

        if self._phase == "latex1":
            bibliography_tool = self._bibliography_tool()
            if bibliography_tool is not None:
                self._start_bibliography(bibliography_tool)
            else:
                self._start_lualatex("latex2")
            return

        if self._phase in {"biber", "bibtex"}:
            self._start_lualatex("latex2")
            return

        if self._phase == "latex2":
            self._start_lualatex("latex3")
            return

        if self._phase == "latex3":
            self._complete()

    def _complete(self) -> None:
        produced_pdf = self._temp_dir / f"{self._stem}.pdf"
        try:
            if not produced_pdf.is_file():
                raise OSError(f"Expected PDF was not created: {produced_pdf}")
            self._destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(produced_pdf, self._destination_path)
        except OSError as exc:
            self._fail(str(exc))
            return

        destination = self._destination_path
        self._cleanup()
        self._window.statusBar().showMessage(
            f"Exported PDF to {destination}",
            5000,
        )

    def _fail(self, message: str) -> None:
        self._cleanup()
        QMessageBox.critical(
            self._window,
            "Export PDF",
            "PDF export failed.\n\n" + str(message),
        )

    def _cleanup(self) -> None:
        try:
            if self._process.state() != QProcess.ProcessState.NotRunning:
                self._process.kill()
                self._process.waitForFinished(250)
        except RuntimeError:
            pass
        shutil.rmtree(self._temp_dir, ignore_errors=True)
        self._window._nd_pdf_export_in_progress = False
        self._window._nd_pdf_export_job = None
        export_action = getattr(self._window, "_export_action", None)
        if export_action is not None:
            export_action.setEnabled(True)


class _PreviewPdfExportJob:
    """Export a fragment by rendering the latest editor text through the existing Preview wrapper."""

    def __init__(
        self,
        window: MainWindow,
        source_path: Path,
        destination_path: Path,
        source: str,
    ) -> None:
        self._window = window
        self._source_path = source_path
        self._destination_path = destination_path
        self._source = source
        self._renderer = window._renderer
        self._renderer_was_enabled = bool(self._renderer.enabled)
        self._finished = False

    def start(self) -> None:
        self._renderer.rendered.connect(self._on_rendered)
        self._renderer.failed.connect(self._on_failed)
        if not self._renderer_was_enabled:
            self._renderer.set_enabled(True)
        self._renderer.render(
            self._source,
            source_path=self._source_path,
            immediate=True,
        )

    def _on_failed(self, message: str) -> None:
        self._cleanup()
        QMessageBox.critical(
            self._window,
            "Export PDF",
            "PDF export failed.\n\n" + str(message),
        )

    def _on_rendered(self, rendered_path: str) -> None:
        rendered_pdf = Path(rendered_path).expanduser()
        try:
            if not rendered_pdf.is_file():
                raise OSError("Rendered preview PDF was not created.")
            self._destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(rendered_pdf, self._destination_path)
        except OSError as exc:
            self._cleanup()
            QMessageBox.critical(self._window, "Export PDF", str(exc))
            return
        destination = self._destination_path
        self._cleanup()
        self._window.statusBar().showMessage(
            f"Exported PDF to {destination}",
            5000,
        )

    def _cleanup(self) -> None:
        if self._finished:
            return
        self._finished = True
        try:
            self._renderer.rendered.disconnect(self._on_rendered)
        except (RuntimeError, TypeError):
            pass
        try:
            self._renderer.failed.disconnect(self._on_failed)
        except (RuntimeError, TypeError):
            pass
        if not self._renderer_was_enabled:
            self._renderer.set_enabled(False)
        self._window._nd_pdf_export_in_progress = False
        self._window._nd_pdf_export_job = None
        export_action = getattr(self._window, "_export_action", None)
        if export_action is not None:
            export_action.setEnabled(True)


class _MainWindowLayoutAndExportFixes:
    """Keep real pane widths persistent and provide reliable PDF export."""

    _installed = False
    _original_set_preview_enabled: Callable | None = None
    _original_save_ui_layout_state: Callable | None = None

    @classmethod
    def install(cls) -> None:
        if cls._installed:
            return

        cls._original_set_preview_enabled = MainWindow._set_preview_enabled
        cls._original_save_ui_layout_state = MainWindow._save_ui_layout_state

        def set_preview_enabled(
            window: MainWindow,
            enabled: bool,
            refresh: bool = True,
        ) -> None:
            cls._set_preview_enabled(window, enabled, refresh)

        def save_ui_layout_state(window: MainWindow) -> None:
            cls._save_ui_layout_state(window)

        def export_pdf(window: MainWindow) -> None:
            cls._export_pdf(window)

        MainWindow._set_preview_enabled = set_preview_enabled
        MainWindow._save_ui_layout_state = save_ui_layout_state
        MainWindow._export_pdf = export_pdf
        cls._installed = True

    @staticmethod
    def _coerce_sizes(value) -> list[int] | None:
        raw = value
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (TypeError, ValueError, json.JSONDecodeError):
                return None
        if not isinstance(raw, (list, tuple)) or len(raw) != 3:
            return None
        try:
            sizes = [max(int(item), 0) for item in raw]
        except (TypeError, ValueError):
            return None
        return sizes if sum(sizes) > 0 else None

    @classmethod
    def _valid_visible_sizes(cls, sizes) -> list[int] | None:
        values = cls._coerce_sizes(sizes)
        if values is None:
            return None
        if values[0] < 60 or values[1] < 160 or values[2] < 120:
            return None
        return values

    @staticmethod
    def _all_main_panes_explicitly_visible(window: MainWindow) -> bool:
        return not any(
            widget.isHidden()
            for widget in (
                window._navigator_splitter,
                window._editor_panel,
                window._preview_panel,
            )
        )

    @classmethod
    def _remember_visible_sizes(cls, window: MainWindow, sizes) -> list[int] | None:
        values = cls._valid_visible_sizes(sizes)
        if values is None:
            return None
        window._nd_last_visible_main_splitter_sizes = list(values)
        try:
            window._session_settings.setValue(
                "ui/main_splitter_visible_sizes_json",
                json.dumps(values),
            )
            window._session_settings.sync()
        except (AttributeError, RuntimeError):
            pass
        return values

    @classmethod
    def _fallback_visible_sizes(cls, window: MainWindow) -> list[int]:
        current = cls._coerce_sizes(window._splitter.sizes()) or [320, 760, 480]
        total = sum(current)
        if total < 700:
            total = max(int(window.width()) - 20, 700)
        navigator = max(int(total * 0.205), 160)
        editor = max(int(total * 0.487), 340)
        preview = max(total - navigator - editor, 240)
        overflow = navigator + editor + preview - total
        if overflow > 0:
            editor = max(editor - overflow, 300)
        return [navigator, editor, preview]

    @classmethod
    def _stored_visible_sizes(cls, window: MainWindow) -> list[int]:
        remembered = cls._valid_visible_sizes(
            getattr(window, "_nd_last_visible_main_splitter_sizes", None)
        )
        if remembered is not None:
            return remembered

        try:
            stored = window._session_settings.value(
                "ui/main_splitter_visible_sizes_json",
                "",
            )
        except (AttributeError, RuntimeError):
            stored = ""
        remembered = cls._valid_visible_sizes(stored)
        if remembered is not None:
            window._nd_last_visible_main_splitter_sizes = list(remembered)
            return remembered

        deferred = cls._valid_visible_sizes(
            getattr(window, "_deferred_main_splitter_sizes", None)
        )
        if deferred is not None:
            cls._remember_visible_sizes(window, deferred)
            return deferred

        current = cls._valid_visible_sizes(window._splitter.sizes())
        if current is not None:
            cls._remember_visible_sizes(window, current)
            return current

        fallback = cls._fallback_visible_sizes(window)
        cls._remember_visible_sizes(window, fallback)
        return fallback

    @classmethod
    def _persist_main_sizes(cls, window: MainWindow, sizes: list[int]) -> None:
        try:
            window._session_settings.setValue(
                "ui/main_splitter_sizes_json",
                json.dumps(sizes),
            )
            window._session_settings.setValue(
                "ui/main_splitter_visible_sizes_json",
                json.dumps(sizes),
            )
            window._session_settings.sync()
        except (AttributeError, RuntimeError):
            pass

        try:
            state = window._read_ui_state_file()
            if not isinstance(state, dict):
                state = {}
            state["main_splitter_sizes"] = list(sizes)
            window._write_ui_state_file(state)
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
            pass

    @classmethod
    def _restore_preview_widths(cls, window: MainWindow) -> None:
        if not bool(getattr(window, "_preview_enabled", False)):
            return
        if window._preview_panel.isHidden():
            return
        sizes = cls._stored_visible_sizes(window)
        window._nd_restoring_preview_splitter = True
        try:
            window._splitter.setSizes(sizes)
        finally:
            window._nd_restoring_preview_splitter = False
        if cls._all_main_panes_explicitly_visible(window):
            cls._remember_visible_sizes(window, window._splitter.sizes())

    @classmethod
    def _set_preview_enabled(
        cls,
        window: MainWindow,
        enabled: bool,
        refresh: bool = True,
    ) -> None:
        original = cls._original_set_preview_enabled
        if original is None:
            return

        enabled = bool(enabled)
        restoring_session = bool(getattr(window, "_restoring_session", False))
        if (
            not enabled
            and not restoring_session
            and cls._all_main_panes_explicitly_visible(window)
        ):
            cls._remember_visible_sizes(window, window._splitter.sizes())

        original(window, enabled, refresh)

        if not enabled:
            cls._persist_main_sizes(window, cls._stored_visible_sizes(window))
            return

        for delay_ms in (0, 120, 280):
            QTimer.singleShot(
                delay_ms,
                lambda target=window: cls._restore_preview_widths(target),
            )

    @classmethod
    def _save_ui_layout_state(cls, window: MainWindow) -> None:
        original = cls._original_save_ui_layout_state
        if original is None:
            return
        original(window)

        if bool(getattr(window, "_restoring_session", False)):
            return
        if bool(getattr(window, "_nd_restoring_preview_splitter", False)):
            return

        if cls._all_main_panes_explicitly_visible(window):
            remembered = cls._remember_visible_sizes(window, window._splitter.sizes())
            if remembered is not None:
                cls._persist_main_sizes(window, remembered)
            return

        cls._persist_main_sizes(window, cls._stored_visible_sizes(window))

    @classmethod
    def _export_pdf(cls, window: MainWindow) -> None:
        if bool(getattr(window, "_nd_pdf_export_in_progress", False)):
            window.statusBar().showMessage("PDF export is already running", 2500)
            return

        source_path = window._editor_panel.current_path()
        if source_path is None:
            QMessageBox.information(window, "Export PDF", "Open a LaTeX document first.")
            return
        source_path = Path(source_path).expanduser().resolve()
        if source_path.suffix.lower() not in {".tex", ".ltx", ".tikz"}:
            QMessageBox.information(
                window,
                "Export PDF",
                "The current tab is not a LaTeX document.",
            )
            return

        source = window._editor_panel.current_content()
        if not window._save_document(source_path, source, show_error=True):
            return
        window._editor_panel.mark_saved(source_path)
        window._save_action.setEnabled(False)

        destination, _ = QFileDialog.getSaveFileName(
            window,
            "Export PDF",
            str(source_path.with_suffix(".pdf")),
            "PDF files (*.pdf)",
        )
        if not destination:
            return

        destination_path = Path(destination).expanduser()
        if destination_path.suffix.lower() != ".pdf":
            destination_path = destination_path.with_suffix(".pdf")

        window._nd_pdf_export_in_progress = True
        export_action = getattr(window, "_export_action", None)
        if export_action is not None:
            export_action.setEnabled(False)

        if "\\documentclass" in source:
            job = _CanonicalPdfExportJob(window, source_path, destination_path)
        else:
            job = _PreviewPdfExportJob(
                window,
                source_path,
                destination_path,
                source,
            )
        window._nd_pdf_export_job = job
        job.start()


class MindMirrorApplication(QApplication):
    """Own QApplication startup and the lifetime of the enhanced main editor window."""

    @classmethod
    def run(cls, argv: list[str]) -> int:
        """Refresh the iPad package, create Qt, show EnhancedMainWindow, and return the event-loop exit code."""
        _refresh_ipad_package()
        EditorInteractionEnhancements.install()
        PersistentEditorVisuals.install()
        _MainWindowLayoutAndExportFixes.install()
        LateRuntimeFixes.install_class_patches()
        _log("Creating QApplication")
        application = cls(argv)
        application.setApplicationName("nd_mind_mirror_project")
        application.setApplicationDisplayName("Mind Mirror")
        application.setOrganizationName("nd_mind_mirror")
        application._late_runtime_objects = LateRuntimeFixes.install_application(application)

        try:
            application.setDesktopFileName("nd-mind-mirror")
        except (AttributeError, TypeError):
            pass

        application.aboutToQuit.connect(lambda: _log("QApplication aboutToQuit"))
        application.lastWindowClosed.connect(lambda: _log("QApplication lastWindowClosed"))

        try:
            icon = build_mind_mirror_icon()
            if not icon.isNull():
                application.setWindowIcon(icon)
            _log("Constructing EnhancedMainWindow")
            window = EnhancedMainWindow()
            window._workspace_interaction_controller = WorkspaceInteractionController(
                window
            )
            window._navigator_stability_controller = NavigatorStabilityController(
                window
            )
            window._late_runtime_window_object = LateRuntimeFixes.install_window(window)
            if not icon.isNull():
                window.setWindowIcon(icon)
            window.destroyed.connect(lambda: _log("EnhancedMainWindow QObject destroyed"))
            window.show()
            _log("EnhancedMainWindow shown; entering Qt event loop")
        except BaseException:
            _log("Exception during EnhancedMainWindow startup:\n" + traceback.format_exc())
            raise

        previous_sigint = signal.getsignal(signal.SIGINT)

        def _handle_sigint(_signum, _frame) -> None:
            """Close the main window cleanly when Ctrl+C sends SIGINT from the launching terminal."""
            _log("SIGINT received; requesting EnhancedMainWindow close")
            QTimer.singleShot(0, window.close)

        signal.signal(signal.SIGINT, _handle_sigint)

        sigint_heartbeat = QTimer(application)
        sigint_heartbeat.setInterval(100)
        sigint_heartbeat.timeout.connect(lambda: None)
        sigint_heartbeat.start()

        try:
            code = application.exec()
        finally:
            sigint_heartbeat.stop()
            signal.signal(signal.SIGINT, previous_sigint)

        _log(f"QApplication.exec returned {code}")
        return code
