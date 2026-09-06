"""Persist editor snapshots in the background without racing path operations."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
import os
from pathlib import Path
from typing import Callable, Iterable

from PySide6.QtCore import QObject, Signal


class DocumentAutosaveController(QObject):
    """Persist immutable editor snapshots outside the GUI thread."""

    _write_finished = Signal(str, int, bool, str, str)

    def __init__(
        self,
        editor_panel,
        protected_path: str | Path | None,
        on_written: Callable[[Path], None],
        parent=None,
    ) -> None:
        """Create the single-worker snapshot writer and path-operation guards."""
        super().__init__(parent)
        self._editor_panel = editor_panel
        self._protected_path = self._resolve_optional_path(protected_path)
        self._on_written = on_written
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="nd_mind_mirror_autosave",
        )
        self._pending_paths: set[Path] = set()
        self._pending_destinations: dict[Path, Path | None] = {}
        self._blocked_roots: set[Path] = set()
        self._write_finished.connect(self._on_write_finished)

    @property
    def has_pending_writes(self) -> bool:
        """Return whether at least one immutable snapshot is still in flight."""
        return bool(self._pending_paths)

    def has_pending_writes_under(self, paths: Iterable[str | Path]) -> bool:
        """Return whether an in-flight snapshot belongs to any supplied path tree."""
        roots = self._normalized_roots(paths)
        if not roots:
            return False
        for source in self._pending_paths:
            destination = self._pending_destinations.get(source, source)
            candidates = (source,) if destination is None else (source, destination)
            if any(
                self._same_or_child(candidate, root)
                for candidate in candidates
                for root in roots
            ):
                return True
        return False

    def block_paths_under(self, paths: Iterable[str | Path]) -> None:
        """Suspend new autosaves under paths being moved or deleted."""
        self._blocked_roots.update(self._normalized_roots(paths))

    def unblock_paths_under(self, paths: Iterable[str | Path]) -> None:
        """Resume autosave after a filesystem operation has reached a stable state."""
        for root in self._normalized_roots(paths):
            self._blocked_roots.discard(root)

    def save_modified(self) -> None:
        """Capture immutable snapshots quickly and stage them in one worker."""
        for path, revision, pieces in self._editor_panel.autosave_snapshots():
            resolved = Path(path).expanduser().resolve(strict=False)
            if self._protected_path is not None and resolved == self._protected_path:
                continue
            if self._is_blocked(resolved) or resolved in self._pending_paths:
                continue

            self._pending_paths.add(resolved)
            self._pending_destinations[resolved] = resolved
            future = self._executor.submit(
                self._write_snapshot_to_temp,
                resolved,
                tuple(pieces),
            )
            future.add_done_callback(
                lambda task, saved_path=resolved, saved_revision=int(revision):
                self._publish_result(task, saved_path, saved_revision)
            )

    def remap_paths_under(
        self,
        old_path: str | Path,
        new_path: str | Path,
    ) -> None:
        """Redirect any still-pending snapshot destination after a successful move."""
        old_root = Path(old_path).expanduser().resolve(strict=False)
        new_root = Path(new_path).expanduser().resolve(strict=False)
        for source in list(self._pending_paths):
            destination = self._pending_destinations.get(source, source)
            if destination is None:
                continue
            try:
                relative = destination.relative_to(old_root)
            except ValueError:
                continue
            self._pending_destinations[source] = (
                new_root / relative
            ).resolve(strict=False)

    def discard_paths_under(self, path: str | Path) -> None:
        """Prevent in-flight snapshots from recreating a deleted path tree."""
        deleted_root = Path(path).expanduser().resolve(strict=False)
        for source in list(self._pending_paths):
            destination = self._pending_destinations.get(source, source)
            if destination is None:
                continue
            if self._same_or_child(destination, deleted_root):
                self._pending_destinations[source] = None

    def shutdown(self) -> None:
        """Stop accepting new snapshots while allowing active writes to finish safely."""
        self._executor.shutdown(wait=False, cancel_futures=False)

    def _publish_result(
        self,
        future: Future,
        path: Path,
        revision: int,
    ) -> None:
        """Publish one worker result back to the GUI thread."""
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
        """Commit a snapshot only while its current path and revision remain valid."""
        source_path = Path(raw_path).expanduser().resolve(strict=False)
        destination = self._pending_destinations.pop(source_path, source_path)
        self._pending_paths.discard(source_path)
        temporary = Path(raw_temporary) if raw_temporary else None

        if not success or temporary is None or destination is None:
            self._remove_temp(temporary)
            return

        destination = destination.expanduser().resolve(strict=False)
        if not self._editor_panel.autosave_revision_matches(destination, revision):
            self._remove_temp(temporary)
            return

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(temporary, destination)
        except OSError:
            self._remove_temp(temporary)
            return

        self._on_written(destination)
        self._editor_panel.mark_saved(destination)

    def _is_blocked(self, path: Path) -> bool:
        """Return whether a path is inside an active filesystem-operation guard."""
        resolved = Path(path).expanduser().resolve(strict=False)
        return any(
            self._same_or_child(resolved, root)
            for root in self._blocked_roots
        )

    @classmethod
    def _normalized_roots(cls, paths: Iterable[str | Path]) -> set[Path]:
        """Normalize a path collection and collapse descendant duplicates."""
        normalized: list[Path] = []
        for value in paths:
            try:
                candidate = Path(value).expanduser().resolve(strict=False)
            except (OSError, TypeError, ValueError):
                continue
            if candidate not in normalized:
                normalized.append(candidate)
        normalized.sort(key=lambda value: len(value.parts))
        roots: set[Path] = set()
        for candidate in normalized:
            if any(cls._same_or_child(candidate, root) for root in roots):
                continue
            roots.add(candidate)
        return roots

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
        """Remove a staged snapshot that must not be committed."""
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
        """Normalize an optional path without raising on invalid configuration."""
        if value is None:
            return None
        try:
            return Path(value).expanduser().resolve(strict=False)
        except (OSError, TypeError, ValueError):
            return None

    @staticmethod
    def _same_or_child(candidate: Path, root: Path) -> bool:
        """Return whether candidate is root or one of its descendants."""
        if candidate == root:
            return True
        try:
            candidate.relative_to(root)
            return True
        except ValueError:
            return False
