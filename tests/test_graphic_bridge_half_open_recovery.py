"""Regression checks for automatic iPad reverse-connection recovery."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVISION = (
    ROOT
    / "src/nd_mind_mirror/graphic/bridge/revision_aware_server.py"
).read_text(encoding="utf-8")
HEALTH = (
    ROOT
    / "src/nd_mind_mirror/graphic/bridge/reverse_tcp_connection_health_policy.py"
).read_text(encoding="utf-8")


def test_reverse_connection_uses_aggressive_tcp_liveness() -> None:
    assert "SO_KEEPALIVE" in HEALTH
    assert "TCP_KEEPIDLE" in HEALTH
    assert "TCP_KEEPINTVL" in HEALTH
    assert "TCP_KEEPCNT" in HEALTH
    assert "TCP_USER_TIMEOUT" in HEALTH


def test_open_request_is_not_marked_delivered_immediately_after_send() -> None:
    pending = REVISION.split(
        "    async def _deliver_pending_open_request", 1
    )[1].split(
        "    async def _serve_reverse_ipad", 1
    )[0]

    assert "_schedule_delivery_confirmation(" in pending
    assert "_last_delivered_open_request_mtime_ns = request_mtime" not in pending


def test_failed_health_window_keeps_request_pending_for_reconnect() -> None:
    confirm = REVISION.split(
        "    async def _confirm_delivery_after_health_window", 1
    )[1].split(
        "    def _mark_open_request_delivered", 1
    )[0]

    assert "writer in self.tcp_clients" in confirm
    assert "did not survive health window" in confirm
    assert "_mark_open_request_delivered(" in confirm


def test_reconnect_resends_pending_open_request() -> None:
    assert "await self._deliver_pending_open_request(writer)" in REVISION
    assert "Resent pending explicit iPad open request after reconnect" in REVISION
