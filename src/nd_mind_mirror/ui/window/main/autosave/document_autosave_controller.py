from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
import os
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, Signal


class DocumentAutosaveController(QObject):
    """Persist immutable editor snapshots outside the GUI thread.

    The worker writes only a temporary file. The GUI thread atomically commits
    that temporary snapshot only if the editor revision still matches the
    captured revision, so an older autosave can never overwrite newer typing.
    """

    _write_finished = Signal(str, int, bool, str, str)

    def __init__(
        self,
        editor_panel,
        protected_path: str | Path | None,
        on_written: Callable[[Path], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._editor_panel = editor_panel
        self._protected_path = self._resolve_optional_path(protected_path)
        self._on_written = on_written
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="nd_mind_mirror_autosave",
        )
        self._pending_paths: set[Path] = set()
        self._write_finished.connect(self._on_write_finished)

    @property
    def has_pending_writes(self) -> bool:
        return bool(self._pending_paths)

    def save_modified(self) -> None:
        """Capture immutable snapshots quickly and stage them in one worker."""
        for path, revision, pieces in self._editor_panel.autosave_snapshots():
            resolved = Path(path).expanduser().resolve()
            if self._protected_path is not None and resolved == self._protected_path:
                continue
            if resolved in self._pending_paths:
                continue

            self._pending_paths.add(resolved)
            future = self._executor.submit(
                self._write_snapshot_to_temp,
                resolved,
                tuple(pieces),
            )
            future.add_done_callback(
                lambda task, saved_path=resolved, saved_revision=int(revision):
                self._publish_result(task, saved_path, saved_revision)
            )

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=False)

    def _publish_result(
        self,
        future: Future,
        path: Path,
        revision: int,
    ) -> None:
        try:
            temporary = Path(future.result())
            self._write_finished.emit(
                str(path),
                int(revision),
                True,
                "",
                str(temporary),
            )
        except Exception as exc:
            self._write_finished.emit(
                str(path),
                int(revision),
                False,
                str(exc),
                "",
            )

    def _on_write_finished(
        self,
        raw_path: str,
        revision: int,
        success: bool,
        _message: str,
        raw_temporary: str,
    ) -> None:
        path = Path(raw_path).expanduser().resolve()
        self._pending_paths.discard(path)
        temporary = Path(raw_temporary) if raw_temporary else None

        if not success or temporary is None:
            self._remove_temp(temporary)
            return

        if not self._editor_panel.autosave_revision_matches(path, revision):
            self._remove_temp(temporary)
            return

        try:
            os.replace(temporary, path)
        except OSError:
            self._remove_temp(temporary)
            return

        self._on_written(path)
        self._editor_panel.mark_saved(path)

    @staticmethod
    def _write_snapshot_to_temp(path: Path, pieces: tuple[str, ...]) -> Path:
        """Write chunk references directly without joining the large source."""
        temporary = path.with_name(f".{path.name}.nd_autosave.tmp")
        original_mode: int | None = None
        try:
            try:
                original_mode = path.stat().st_mode
            except OSError:
                original_mode = None

            with temporary.open("w", encoding="utf-8", newline="") as handle:
                for piece in pieces:
                    handle.write(piece)
                handle.flush()
                os.fsync(handle.fileno())

            if original_mode is not None:
                os.chmod(temporary, original_mode)
            return temporary
        except Exception:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
            raise

    @staticmethod
    def _remove_temp(path: Path | None) -> None:
        if path is None:
            return
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass

    @staticmethod
    def _resolve_optional_path(value: str | Path | None) -> Path | None:
        if value is None:
            return None
        try:
            return Path(value).expanduser().resolve()
        except (OSError, TypeError, ValueError):
            return None
