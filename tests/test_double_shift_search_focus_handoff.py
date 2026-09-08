"""Regression checks for lossless Double-Shift Search focus handoff."""

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOUBLE_SHIFT = (
    PROJECT_ROOT
    / "src/nd_mind_mirror/ui/input/double_shift/double_shift_event_filter.py"
)
HANDOFF = (
    PROJECT_ROOT
    / "src/nd_mind_mirror/ui/input/double_shift/activation_key_handoff_buffer.py"
)


def _function_source(path: Path, name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(lines[node.lineno - 1:node.end_lineno])
    raise AssertionError(f"{name} not found in {path}")


def test_double_shift_arms_handoff_before_search_signal() -> None:
    source = _function_source(DOUBLE_SHIFT, "_handle_key_release")
    assert "self._activation_handoff.begin()" in source
    assert "self.activated.emit()" in source
    assert source.index("self._activation_handoff.begin()") < source.index(
        "self.activated.emit()"
    )
    assert "return True" in source


def test_application_filter_gives_handoff_first_refusal() -> None:
    source = _function_source(DOUBLE_SHIFT, "eventFilter")
    assert "self._activation_handoff.intercept(watched, event)" in source
    assert source.index("self._activation_handoff.intercept") < source.index(
        "event_type = event.type()"
    )


def test_handoff_captures_old_target_keys_and_replays_in_order() -> None:
    source = HANDOFF.read_text(encoding="utf-8")
    intercept = _function_source(HANDOFF, "intercept")
    finish = _function_source(HANDOFF, "_finish_handoff")

    assert "isinstance(watched, QLineEdit)" in intercept
    assert "QEvent.Type.KeyPress" in intercept
    assert "return self._capture_key_press(event)" in intercept
    assert "pending = tuple(self._pending_key_presses)" in finish
    assert "for key, modifiers, text, auto_repeat, count in pending:" in finish
    assert "QApplication.sendEvent(target, replay)" in finish
    assert "dataclass" not in source


def test_handoff_has_bounded_fail_safe_timeout() -> None:
    source = HANDOFF.read_text(encoding="utf-8")
    assert "_DEFAULT_TIMEOUT_MS = 1200" in source
    assert "self._timeout_timer.setSingleShot(True)" in source
    assert "self._timeout_timer.timeout.connect(self.cancel)" in source
