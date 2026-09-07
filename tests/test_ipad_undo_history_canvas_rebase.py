from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IPAD = ROOT / "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm"


def _read(relative: str) -> str:
    return (IPAD / relative).read_text(encoding="utf-8")


def test_native_pencilkit_undo_registration_is_disabled_at_canvas_creation() -> None:
    lifecycle = _read("Views/PencilCanvasHistoryRebaseController.swift")
    canvas = _read("Views/PencilCanvasView.swift")

    assert "disableUndoRegistration()" in lifecycle
    assert "removeAllActions()" in lifecycle
    assert "levelsOfUndo = 0" not in lifecycle
    assert "levelsOfUndo = 0" not in canvas


def test_programmatic_history_restore_is_intercepted_before_normal_drawing_callback() -> None:
    canvas = _read("Views/PencilCanvasView.swift")

    callback = canvas.index("func canvasViewDrawingDidChange")
    consume = canvas.index(
        "activeToolController.consumeProgrammaticDrawingChange(canvasView.drawing)",
        callback,
    )
    user_callback = canvas.index("onDrawingChanged(canvasView.drawing)", callback)
    assert consume < user_callback
    assert "pendingHistoryCanvasReplacement = true" in canvas[consume:user_callback]


def test_history_restore_replaces_only_internal_pencilkit_surface() -> None:
    canvas = _read("Views/PencilCanvasView.swift")
    lifecycle = _read("Views/PencilCanvasHistoryRebaseController.swift")

    assert "let historyRestoreRequested = coordinator.consumeHistoryRestoreRequest" in canvas
    assert "if documentTokenChanged || historyRestoreRequested" in canvas
    assert "coordinator.replaceCanvas(" in canvas
    assert "contentView.insertSubview(replacement" in lifecycle
    assert "currentCanvas.removeFromSuperview()" in lifecycle
    assert "UIScrollView()" not in lifecycle


def test_replacement_reattaches_active_tools_to_the_new_canvas() -> None:
    canvas = _read("Views/PencilCanvasView.swift")

    replacement_method = canvas[canvas.index("func replaceCanvas(") :]
    assert "canvas = replacement" in replacement_method
    assert "activeToolController.attach(" in replacement_method
    assert "canvas: replacement" in replacement_method


def test_app_owned_history_remains_the_single_restore_authority() -> None:
    content = _read("Views/ContentView.swift")
    canvas = _read("Views/PencilCanvasView.swift")

    assert "editHistory.undo()" in content
    assert "editHistory.redo()" in content
    assert "activeTool.applyHistorySnapshot(snapshot)" in content
    assert "activeToolController.consumeProgrammaticDrawingChange" in canvas
