"""Run one workspace reference-usage scan in a standalone child process."""

from __future__ import annotations

import json
import sys

from nd_mind_mirror.core.workspace.operation.reference_usage_scan_service import (
    WorkspaceReferenceUsageScanService,
)


class WorkspaceReferenceUsageScanWorker:
    """Read one scan request from stdin and emit one JSON result to stdout."""

    def run(self) -> int:
        """Execute the request and return a process exit code."""
        try:
            request = json.load(sys.stdin)
            if not isinstance(request, dict):
                raise ValueError("request must be a JSON object")
            result = WorkspaceReferenceUsageScanService().execute(request)
            json.dump(result, sys.stdout, ensure_ascii=False)
            sys.stdout.write("\n")
            sys.stdout.flush()
            return 0 if not result.get("errors") else 2
        except Exception as exc:
            json.dump(
                {"usages_by_target": {}, "errors": [str(exc)]},
                sys.stdout,
                ensure_ascii=False,
            )
            sys.stdout.write("\n")
            sys.stdout.flush()
            return 1


def main() -> int:
    """Run the workspace reference-usage scan worker."""
    return WorkspaceReferenceUsageScanWorker().run()


if __name__ == "__main__":
    raise SystemExit(main())
