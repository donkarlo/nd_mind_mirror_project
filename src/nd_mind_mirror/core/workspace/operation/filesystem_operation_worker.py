"""Run one workspace filesystem operation request as a standalone child process."""

from __future__ import annotations

import json
import sys

from nd_mind_mirror.core.workspace.operation.filesystem_operation_service import (
    WorkspaceFilesystemOperationService,
)


class WorkspaceFilesystemOperationWorker:
    """Translate JSON stdin/stdout around the filesystem operation service."""

    def run(self) -> int:
        """Read one JSON request, execute it, and emit one JSON result."""
        try:
            payload = sys.stdin.buffer.read()
            request = json.loads(payload.decode("utf-8") or "{}")
            if not isinstance(request, dict):
                raise ValueError("Filesystem operation request must be a JSON object.")
            result = WorkspaceFilesystemOperationService().execute(request)
            sys.stdout.write(json.dumps(result, ensure_ascii=False))
            sys.stdout.flush()
            return 0
        except Exception as exc:
            sys.stdout.write(
                json.dumps(
                    {"moves": [], "deletes": [], "worker_error": str(exc)},
                    ensure_ascii=False,
                )
            )
            sys.stdout.flush()
            return 1


if __name__ == "__main__":
    raise SystemExit(WorkspaceFilesystemOperationWorker().run())
