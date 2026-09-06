"""Run one workspace reference-maintenance request as a standalone child process."""

from __future__ import annotations

import json
import sys

from nd_mind_mirror.core.workspace.operation.reference_maintenance_service import (
    WorkspaceReferenceMaintenanceService,
)


class WorkspaceReferenceMaintenanceWorker:
    """Read one JSON request from stdin and emit one JSON result to stdout."""

    def run(self) -> int:
        """Execute the serialized request and return a process exit code."""
        try:
            request = json.load(sys.stdin)
            if not isinstance(request, dict):
                raise ValueError("request must be a JSON object")
            result = WorkspaceReferenceMaintenanceService().execute(request)
            json.dump(result, sys.stdout, ensure_ascii=False)
            sys.stdout.write("\n")
            sys.stdout.flush()
            return 0 if not result.get("errors") else 2
        except Exception as exc:
            json.dump(
                {"changed_files": [], "errors": [str(exc)]},
                sys.stdout,
                ensure_ascii=False,
            )
            sys.stdout.write("\n")
            sys.stdout.flush()
            return 1


def main() -> int:
    """Run the workspace reference-maintenance worker."""
    return WorkspaceReferenceMaintenanceWorker().run()


if __name__ == "__main__":
    raise SystemExit(main())
