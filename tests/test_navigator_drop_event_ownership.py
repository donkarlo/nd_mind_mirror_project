"""Regression tests for Navigator drag-and-drop filesystem ownership."""

from types import SimpleNamespace

from PySide6.QtCore import Qt

from nd_mind_mirror.ui.panel.file_system.file_system_panel import FileSystemPanel


def test_custom_drop_does_not_authorize_qt_native_move() -> None:
    """A handled Navigator drop must not let QFileSystemModel move the source again."""
    calls: list[tuple[str, object]] = []
    event = SimpleNamespace(
        setDropAction=lambda action: calls.append(("drop_action", action)),
        ignore=lambda: calls.append(("ignore", None)),
        acceptProposedAction=lambda: calls.append(("accept_proposed", None)),
    )

    FileSystemPanel._consume_custom_drop(event)

    assert calls == [
        ("drop_action", Qt.DropAction.IgnoreAction),
        ("ignore", None),
    ]
