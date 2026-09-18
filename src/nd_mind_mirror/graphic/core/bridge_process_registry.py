"""Find and remove stale Mind Mirror graphic bridge processes."""

from __future__ import annotations

import os
import signal
import subprocess
import time


class GraphicBridgeProcessRegistry:
    """Own process discovery/cleanup without coupling it to Qt process objects."""

    _COMMAND_MARKER = "-m nd_mind_mirror.graphic.bridge"

    def bridge_pids(self) -> tuple[int, ...]:
        """Return bridge PIDs owned by the current Unix user."""
        try:
            completed = subprocess.run(
                [
                    "ps",
                    "-u",
                    str(os.getuid()),
                    "-o",
                    "pid=,args=",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=1.0,
            )
        except (OSError, subprocess.SubprocessError):
            return ()

        current_pid = os.getpid()
        result: list[int] = []
        for raw_line in completed.stdout.splitlines():
            line = raw_line.strip()
            if not line or self._COMMAND_MARKER not in line:
                continue
            pid_text, separator, _command = line.partition(" ")
            if not separator:
                continue
            try:
                pid = int(pid_text)
            except ValueError:
                continue
            if pid != current_pid:
                result.append(pid)
        return tuple(sorted(set(result)))

    def terminate_all(self, *, graceful_timeout_seconds: float = 0.8) -> tuple[int, ...]:
        """Terminate every stale bridge and force-kill only processes that remain."""
        pids = self.bridge_pids()
        if not pids:
            return ()

        for pid in pids:
            self._signal(pid, signal.SIGTERM)

        deadline = time.monotonic() + max(float(graceful_timeout_seconds), 0.0)
        remaining = set(pids)
        while remaining and time.monotonic() < deadline:
            remaining = {pid for pid in remaining if self._is_alive(pid)}
            if remaining:
                time.sleep(0.04)

        for pid in remaining:
            self._signal(pid, signal.SIGKILL)
        return pids

    @staticmethod
    def _signal(pid: int, sig: signal.Signals) -> None:
        try:
            os.kill(int(pid), sig)
        except (ProcessLookupError, PermissionError, OSError):
            return

    @staticmethod
    def _is_alive(pid: int) -> bool:
        try:
            os.kill(int(pid), 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False
        return True
