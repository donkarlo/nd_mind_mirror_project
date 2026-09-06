"""Keep the active iPad graphic synchronized when its workspace path changes."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import Request

from .graphic_path_alias_registry import GraphicPathAliasRegistry
from .revision_aware_server import RevisionAwareGraphicBridgeServer


class PathAwareGraphicBridgeServer(RevisionAwareGraphicBridgeServer):
    """Keep live iPad sessions valid across file and folder renames."""

    _RENAME_REQUEST_POLL_SECONDS = 0.15

    def __init__(self, *args, **kwargs) -> None:
        self._rename_from_for_next_open: Path | None = None
        self._rename_request_task: asyncio.Task[None] | None = None
        self._last_seen_rename_request_mtime_ns = 0
        self._last_applied_rename_request_key: tuple[str, str, int] | None = None
        super().__init__(*args, **kwargs)
        self._path_aliases = GraphicPathAliasRegistry(self.workspace)
        self.rename_request_path = (
            self.workspace / ".nd_mind_mirror" / "graphic_rename_request.json"
        )
        self.app.post("/rename-graphic")(self.http_rename_graphic)

    async def startup(self) -> None:
        """Restore the last durable alias, then watch new rename requests."""
        self._load_durable_rename_alias()
        await super().startup()
        self._rename_request_task = asyncio.create_task(
            self._watch_durable_rename_requests()
        )

    async def shutdown(self) -> None:
        """Stop the rename watcher before shutting down inherited bridge transports."""
        if self._rename_request_task is not None:
            self._rename_request_task.cancel()
            try:
                await self._rename_request_task
            except asyncio.CancelledError:
                pass
            self._rename_request_task = None
        await super().shutdown()

    async def http_rename_graphic(self, request: Request) -> dict[str, object]:
        """Apply the same rename payload used by the durable filesystem channel."""
        if not self._authorized(request.query_params.get("token", "")):
            return {"ok": False, "error": "Invalid token"}
        payload = await request.json()
        return await self._apply_rename_payload(payload, broadcast=True)

    def _resolve_sidecar(self, relative: str) -> Path:
        """Resolve stale iPad save paths through the rename alias registry."""
        requested = self._workspace_path(relative)
        if requested.suffix.lower() != ".ndgraphic":
            raise ValueError("Graphic document must use .ndgraphic")
        remapped = self._path_aliases.resolve(requested)
        try:
            current_relative = remapped.relative_to(self.workspace).as_posix()
        except ValueError as exc:
            raise ValueError("Graphic path must stay inside the workspace") from exc
        return super()._resolve_sidecar(current_relative)

    async def _watch_durable_rename_requests(self) -> None:
        """Apply rename requests even when the fixed HTTP bridge port is unavailable."""
        while True:
            try:
                mtime = self._rename_request_mtime_ns()
                if mtime > self._last_seen_rename_request_mtime_ns:
                    self._last_seen_rename_request_mtime_ns = mtime
                    payload = json.loads(
                        self.rename_request_path.read_text(encoding="utf-8")
                    )
                    await self._apply_rename_payload(payload, broadcast=True)
                await asyncio.sleep(self._RENAME_REQUEST_POLL_SECONDS)
            except asyncio.CancelledError:
                raise
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                self._log_event(
                    "Durable graphic rename watcher error: "
                    f"{type(exc).__name__}: {exc}"
                )
                await asyncio.sleep(0.5)

    def _load_durable_rename_alias(self) -> None:
        """Load the latest alias at startup without reopening a historical document."""
        self._last_seen_rename_request_mtime_ns = self._rename_request_mtime_ns()
        if self._last_seen_rename_request_mtime_ns <= 0:
            return
        try:
            payload = json.loads(
                self.rename_request_path.read_text(encoding="utf-8")
            )
            old_path, new_path, key = self._rename_payload_paths(payload)
            self._path_aliases.register(old_path, new_path)
            self._last_applied_rename_request_key = key
            self._remap_open_request(old_path, new_path)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            self._log_event(
                "Could not restore durable graphic rename alias: "
                f"{type(exc).__name__}: {exc}"
            )

    async def _apply_rename_payload(
        self,
        payload: object,
        *,
        broadcast: bool,
    ) -> dict[str, object]:
        """Register one rename and remap the active document when it is affected."""
        old_path, new_path, key = self._rename_payload_paths(payload)
        if key == self._last_applied_rename_request_key:
            return {
                "ok": True,
                "active_remapped": self.current_sidecar == self._path_aliases.resolve(new_path),
                "duplicate": True,
            }

        self._path_aliases.register(old_path, new_path)
        previous = self.current_sidecar
        remapped_sidecar = self._remap_candidate(previous, old_path, new_path)
        self._remap_open_request(old_path, new_path)
        self._last_applied_rename_request_key = key

        if (
            remapped_sidecar is None
            or remapped_sidecar.suffix.lower() != ".ndgraphic"
            or not remapped_sidecar.is_file()
        ):
            self._log_event(
                f"Registered graphic path alias old={old_path} new={new_path}"
            )
            return {"ok": True, "active_remapped": False}

        self.current_sidecar = remapped_sidecar
        if broadcast and (self.tcp_clients or self.clients):
            self._rename_from_for_next_open = previous
            try:
                await self._broadcast_open(
                    remapped_sidecar,
                    "open_graphic",
                    operation=self.current_operation,
                )
            finally:
                self._rename_from_for_next_open = None

        self._log_event(
            "Remapped active iPad graphic after workspace rename "
            f"old={previous} new={remapped_sidecar}"
        )
        return {
            "ok": True,
            "active_remapped": True,
            "path": remapped_sidecar.relative_to(self.workspace).as_posix(),
        }

    def _rename_payload_paths(
        self,
        payload: object,
    ) -> tuple[Path, Path, tuple[str, str, int]]:
        """Validate one durable/HTTP rename payload and return canonical paths."""
        if not isinstance(payload, dict):
            raise ValueError("Graphic rename payload must be an object")
        old_raw = str(payload.get("old_path", "")).strip()
        new_raw = str(payload.get("new_path", "")).strip()
        old_path = self._workspace_path(old_raw)
        new_path = self._workspace_path(new_raw)
        try:
            request_id = int(payload.get("request_id", 0))
        except (TypeError, ValueError):
            request_id = 0
        return old_path, new_path, (old_raw, new_raw, request_id)

    def _open_payload(
        self,
        sidecar: Path,
        message_type: str,
        *,
        operation: str | None = None,
        client_revision: int = 0,
    ) -> dict[str, object]:
        """Mark only the immediate post-rename open as an identity remap."""
        payload = super()._open_payload(
            sidecar,
            message_type,
            operation=operation,
            client_revision=client_revision,
        )
        previous = self._rename_from_for_next_open
        document = payload.get("document")
        if previous is None or not isinstance(document, dict):
            return payload
        try:
            renamed_from = previous.relative_to(self.workspace).as_posix()
        except ValueError:
            return payload
        updated_document = dict(document)
        updated_document["renamed_from"] = renamed_from
        payload["document"] = updated_document
        return payload

    def _workspace_path(self, raw_path: str) -> Path:
        """Resolve a relative workspace path without requiring the old path to exist."""
        if not raw_path:
            raise ValueError("Workspace path is empty")
        path = (self.workspace / raw_path).resolve(strict=False)
        try:
            path.relative_to(self.workspace)
        except ValueError as exc:
            raise ValueError("Workspace path must stay inside the workspace") from exc
        return path

    @staticmethod
    def _remap_candidate(
        candidate: Path | None,
        old_path: Path,
        new_path: Path,
    ) -> Path | None:
        """Return candidate under the new path when old_path contains it."""
        if candidate is None:
            return None
        resolved = candidate.expanduser().resolve(strict=False)
        try:
            relative = resolved.relative_to(old_path)
        except ValueError:
            return None
        return (new_path / relative).resolve(strict=False)

    def _remap_open_request(self, old_path: Path, new_path: Path) -> None:
        """Keep the durable desktop open request consistent with a completed rename."""
        try:
            payload = json.loads(self.request_path.read_text(encoding="utf-8"))
            requested = (
                self.workspace / str(payload.get("path", ""))
            ).resolve(strict=False)
            remapped = self._remap_candidate(requested, old_path, new_path)
            if remapped is None or remapped.suffix.lower() != ".ndgraphic":
                return
            payload["path"] = remapped.relative_to(self.workspace).as_posix()
            self.request_path.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )
            request_mtime = self.request_path.stat().st_mtime_ns
            self._last_seen_open_request_mtime_ns = max(
                self._last_seen_open_request_mtime_ns,
                request_mtime,
            )
            self._last_delivered_open_request_mtime_ns = max(
                self._last_delivered_open_request_mtime_ns,
                request_mtime,
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return

    def _rename_request_mtime_ns(self) -> int:
        try:
            return self.rename_request_path.stat().st_mtime_ns
        except OSError:
            return 0
