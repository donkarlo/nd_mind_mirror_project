"""Idempotent iPad fixes applied after the generated hotfix migration."""

from __future__ import annotations

from pathlib import Path
import re


class IpadSourcePostHotfix:
    """Keep the current iPad interaction model and release identity coherent."""

    RELEASE_VERSION = "0.31.13"
    RELEASE_BUILD = "43"

    def __init__(self, source_root: str | Path) -> None:
        self.source_root = Path(source_root).expanduser().resolve()

    def apply(self) -> bool:
        changed = False
        changed |= self._patch_release_version()
        changed |= self._patch_pinch_zoom()
        changed |= self._patch_content_view()
        changed |= self._patch_selection_move_handle()
        return changed

    @staticmethod
    def _write_if_changed(path: Path, original: str, updated: str) -> bool:
        if updated == original:
            return False
        path.write_text(updated, encoding="utf-8")
        return True

    def _patch_release_version(self) -> bool:
        changed = False
        package_path = self.source_root / "Package.swift"
        if package_path.is_file():
            original = package_path.read_text(encoding="utf-8")
            text = re.sub(r'displayVersion:\s*"[^"]+"', f'displayVersion: "{self.RELEASE_VERSION}"', original, count=1)
            text = re.sub(r'bundleVersion:\s*"[^"]+"', f'bundleVersion: "{self.RELEASE_BUILD}"', text, count=1)
            changed |= self._write_if_changed(package_path, original, text)

        app_path = self.source_root / "NDGraphicApp.swift"
        if app_path.is_file():
            original = app_path.read_text(encoding="utf-8")
            text = re.sub(r'Text\("ND Graphic(?: v)? [0-9]+(?:\.[0-9]+)+"\)', f'Text("ND Graphic {self.RELEASE_VERSION}")', original, count=1)
            changed |= self._write_if_changed(app_path, original, text)

        content_path = self.source_root / "Views" / "ContentView.swift"
        if content_path.is_file():
            original = content_path.read_text(encoding="utf-8")
            text = re.sub(r'Text\("ND Graphic v[0-9]+(?:\.[0-9]+)+"\)', f'Text("ND Graphic v{self.RELEASE_VERSION}")', original, count=1)
            changed |= self._write_if_changed(content_path, original, text)

        bridge_path = self.source_root / "Services" / "GraphicBridgeClient.swift"
        if bridge_path.is_file():
            original = bridge_path.read_text(encoding="utf-8")
            text = re.sub(r'"version":\s*"[0-9]+(?:\.[0-9]+)+"', f'"version": "{self.RELEASE_VERSION}"', original, count=1)
            changed |= self._write_if_changed(bridge_path, original, text)
        return changed

    def _patch_pinch_zoom(self) -> bool:
        path = self.source_root / "Views" / "PencilCanvasView.swift"
        if not path.is_file():
            return False
        original = path.read_text(encoding="utf-8")
        text = re.sub(r"(?m)^(\s*)scroll\.minimumZoomScale\s*=\s*1(?:\.0)?\s*$", r"\1scroll.minimumZoomScale = 0.05", original)
        text = re.sub(r"(?m)^(\s*)scroll\.maximumZoomScale\s*=\s*1(?:\.0)?\s*$", r"\1scroll.maximumZoomScale = 10.0", text)
        return self._write_if_changed(path, original, text)

    def _patch_content_view(self) -> bool:
        path = self.source_root / "Views" / "ContentView.swift"
        if not path.is_file():
            return False
        original = path.read_text(encoding="utf-8")
        text = original

        text = text.replace(
            "    @StateObject private var recentPresets = RecentToolPresetStore()\n",
            "    @StateObject private var fixedPresets = FixedToolPresetStore()\n",
        )
        text = text.replace("    @State private var showToolPresets = false\n", "")
        text = text.replace("                    recentPresets.remember(hex: color, width: pencil.width, for: tool)\n", "")
        text = text.replace("                recentPresets.remember(color: newColor, width: pencil.width, for: tool)\n", "")

        old_change = '''        .onChange(of: tool) { oldTool, newTool in
            switchToolColor(from: oldTool, to: newTool)
            showRecentColors = false
            if !newTool.supportsColor {
                showToolPresets = false
            } else {
                recentPresets.remember(color: pencil.color, width: pencil.width, for: newTool)
            }
        }
        .onChange(of: pencil.width) { _, newWidth in
            if tool.supportsWidth {
                recentPresets.remember(color: pencil.color, width: newWidth, for: tool)
            }
        }
'''
        new_change = '''        .onChange(of: tool) { oldTool, newTool in
            switchToolColor(from: oldTool, to: newTool)
            showRecentColors = false
        }
'''
        text = text.replace(old_change, new_change)

        if "ND_FIXED_TOOL_PRESETS_V1" not in text:
            pattern = re.compile(
                r'                // ND_TOOL_BUTTONS_LONG_PRESS_V1\n.*?                \.popover\(isPresented: \$showToolPresets, arrowEdge: \.top\) \{\n                    recentToolPresetPopover\n                \}\n',
                re.S,
            )
            replacement = '''                // ND_FIXED_TOOL_PRESETS_V1
                HStack(spacing: 0) {
                    toolButton(.pencil, systemImage: "pencil")
                    Divider()
                    toolButton(.highlighter, systemImage: "highlighter")
                    Divider()
                    toolButton(.eraser, systemImage: "eraser")
                    Divider()
                    toolButton(.lasso, systemImage: "lasso")
                }
                .frame(width: 184, height: 28)
                .background(
                    Color(uiColor: .secondarySystemBackground),
                    in: RoundedRectangle(cornerRadius: 7)
                )
                .overlay {
                    RoundedRectangle(cornerRadius: 7)
                        .stroke(Color.secondary.opacity(0.25), lineWidth: 0.5)
                }
                .accessibilityLabel("Drawing tool")

                if tool.supportsColor && tool.supportsWidth {
                    HStack(spacing: 4) {
                        ForEach(fixedPresets.presets(for: tool)) { preset in
                            Button {
                                applyFixedPreset(preset)
                            } label: {
                                HStack(spacing: 3) {
                                    Circle()
                                        .fill(Color(hex: preset.colorHex))
                                        .frame(width: 10, height: 10)
                                    Text("\\(preset.slot)")
                                        .font(.caption2.bold())
                                    Text(String(format: "%.1f", preset.width))
                                        .font(.caption2.monospacedDigit())
                                }
                            }
                            .buttonStyle(.bordered)
                            .controlSize(.mini)
                            .help("Use saved \\(tool.rawValue) preset \\(preset.slot)")
                        }

                        Menu {
                            ForEach(1...4, id: \.self) { slot in
                                Button("Save current to slot \\(slot)") {
                                    fixedPresets.save(
                                        slot: slot,
                                        color: pencil.color,
                                        width: pencil.width,
                                        for: tool
                                    )
                                }
                            }
                        } label: {
                            Image(systemName: "square.and.arrow.down")
                                .frame(width: 24, height: 24)
                        }
                        .help("Save current color and thickness to one of four permanent slots")
                    }
                }
'''
            match = pattern.search(text)
            if match is not None:
                text = text[:match.start()] + replacement + text[match.end():]

        if "private func toolButton(" not in text:
            insertion = '''
    @ViewBuilder
    private func toolButton(_ target: GraphicTool, systemImage: String) -> some View {
        Button {
            tool = target
        } label: {
            Image(systemName: systemImage)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .buttonStyle(.plain)
        .background(tool == target ? Color.accentColor.opacity(0.18) : Color.clear)
        .contentShape(Rectangle())
    }

    private func applyFixedPreset(_ preset: FixedToolPreset) {
        guard tool.supportsColor && tool.supportsWidth else { return }
        pencil.color = Color(hex: preset.colorHex)
        pencil.width = preset.width
        recentColors.remember(hex: preset.colorHex, for: tool)
    }

'''
            anchor = "    /// Binds the color picker to the current tool and records its choice only in that tool's history.\n"
            text = text.replace(anchor, insertion + anchor, 1)

        popover_pattern = re.compile(
            r'    private var recentToolPresetPopover: some View \{.*?\n    \}\n\n(?=    /// Binds the color picker)',
            re.S,
        )
        text = popover_pattern.sub("", text, count=1)
        return self._write_if_changed(path, original, text)

    def _patch_selection_move_handle(self) -> bool:
        path = self.source_root / "Views" / "PencilCanvasView.swift"
        if not path.is_file():
            return False
        original = path.read_text(encoding="utf-8")
        if "ND_SELECTION_MOVE_HANDLE_V1" in original:
            return False
        text = original

        text = text.replace(
            "    let handles: [UIView]\n    private var selectionBounds: CGRect?\n",
            "    let handles: [UIView]\n    let moveHandle: UIView\n    private var selectionBounds: CGRect?\n",
            1,
        )
        text = text.replace(
            "        handles = Corner.allCases.map { corner in\n",
            "        // ND_SELECTION_MOVE_HANDLE_V1\n        handles = Corner.allCases.map { corner in\n",
            1,
        )
        text = text.replace(
            "        super.init(frame: frame)\n",
            "        moveHandle = UIView()\n        super.init(frame: frame)\n",
            1,
        )
        text = text.replace(
            "        for handle in handles {\n            addSubview(handle)\n        }\n",
            '''        for handle in handles {
            addSubview(handle)
        }
        moveHandle.backgroundColor = .systemBlue
        moveHandle.layer.borderColor = UIColor.white.cgColor
        moveHandle.layer.borderWidth = 1.5
        moveHandle.isUserInteractionEnabled = true
        addSubview(moveHandle)
''',
            1,
        )
        text = text.replace(
            "        for corner in Corner.allCases {\n",
            '''        let moveWidth = 46.0 / scale
        let moveHeight = 24.0 / scale
        moveHandle.bounds = CGRect(x: 0, y: 0, width: moveWidth, height: moveHeight)
        moveHandle.center = CGPoint(
            x: bounds.midX,
            y: max(moveHeight / 2, bounds.minY - 16.0 / scale)
        )
        moveHandle.layer.cornerRadius = moveHeight / 2
        moveHandle.layer.borderWidth = max(1.5 / scale, 0.6)

        for corner in Corner.allCases {
''',
            1,
        )
        text = text.replace(
            "        for handle in handles.reversed() {\n",
            '''        let movePoint = moveHandle.convert(point, from: self)
        if moveHandle.point(inside: movePoint, with: event) {
            return moveHandle
        }
        for handle in handles.reversed() {
''',
            1,
        )
        text = text.replace(
            "        let twoFingerUndo = UITapGestureRecognizer(\n",
            '''        let moveSelection = UIPanGestureRecognizer(
            target: context.coordinator,
            action: #selector(Coordinator.handleMoveSelection(_:))
        )
        moveSelection.maximumNumberOfTouches = 1
        moveSelection.allowedTouchTypes = [NSNumber(value: UITouch.TouchType.direct.rawValue)]
        moveSelection.delegate = context.coordinator
        selectionOverlay.moveHandle.addGestureRecognizer(moveSelection)
        scroll.panGestureRecognizer.require(toFail: moveSelection)

        let twoFingerUndo = UITapGestureRecognizer(
''',
            1,
        )
        text = text.replace(
            "        private struct ResizeSession {\n",
            '''        private struct MoveSession {
            let originalDrawing: PKDrawing
            let selectedIndices: [Int]
            let originalBounds: CGRect
        }

        private struct ResizeSession {
''',
            1,
        )
        text = text.replace(
            "        private var resizeSession: ResizeSession?\n",
            "        private var resizeSession: ResizeSession?\n        private var moveSession: MoveSession?\n",
            1,
        )
        text = text.replace(
            "            if resizeSession == nil && !selectedStrokeIndices.isEmpty {\n",
            "            if resizeSession == nil && moveSession == nil && !selectedStrokeIndices.isEmpty {\n",
            1,
        )

        move_methods = r'''        /// Moves the entire current lasso selection by dragging the blue pill handle.
        @objc func handleMoveSelection(_ recognizer: UIPanGestureRecognizer) {
            guard activeTool == .lasso,
                  let overlay = selectionOverlay,
                  let canvas = canvas,
                  let bounds = currentSelectionBounds(in: canvas.drawing),
                  !selectedStrokeIndices.isEmpty else { return }

            switch recognizer.state {
            case .began:
                moveSession = MoveSession(
                    originalDrawing: canvas.drawing,
                    selectedIndices: selectedStrokeIndices,
                    originalBounds: bounds
                )
            case .changed, .ended:
                guard let session = moveSession else { return }
                let raw = recognizer.translation(in: overlay)
                let dx = min(
                    max(raw.x, -session.originalBounds.minX),
                    logicalCanvasSize.width - session.originalBounds.maxX
                )
                let dy = min(
                    max(raw.y, -session.originalBounds.minY),
                    logicalCanvasSize.height - session.originalBounds.maxY
                )
                applyMove(
                    dx: dx,
                    dy: dy,
                    session: session,
                    canvas: canvas,
                    overlay: overlay
                )
                if recognizer.state == .ended {
                    let finalDrawing = canvas.drawing
                    moveSession = nil
                    registerMoveUndo(original: session.originalDrawing, final: finalDrawing)
                    onDrawingChanged(finalDrawing)
                    onUndoManagerChanged(canvas.undoManager)
                }
            case .cancelled, .failed:
                if let session = moveSession {
                    loading = true
                    canvas.drawing = session.originalDrawing
                    loading = false
                    moveSession = nil
                    refreshSelectionBounds()
                }
            default:
                break
            }
        }

        private func applyMove(
            dx: CGFloat,
            dy: CGFloat,
            session: MoveSession,
            canvas: PKCanvasView,
            overlay: SelectionResizeOverlay
        ) {
            let transform = CGAffineTransform(translationX: dx, y: dy)
            var selectedStrokes: [PKStroke] = []
            var validIndices: [Int] = []
            for index in session.selectedIndices
            where index >= 0 && index < session.originalDrawing.strokes.count {
                selectedStrokes.append(session.originalDrawing.strokes[index])
                validIndices.append(index)
            }
            guard !selectedStrokes.isEmpty else { return }

            var selectedDrawing = PKDrawing(strokes: selectedStrokes)
            selectedDrawing.transform(using: transform)
            var allStrokes = session.originalDrawing.strokes
            for (offset, index) in validIndices.enumerated()
            where offset < selectedDrawing.strokes.count {
                allStrokes[index] = selectedDrawing.strokes[offset]
            }
            loading = true
            canvas.drawing = PKDrawing(strokes: allStrokes)
            loading = false
            overlay.setSelection(
                bounds: session.originalBounds.offsetBy(dx: dx, dy: dy),
                zoomScale: scrollView?.zoomScale ?? 1.0
            )
        }

'''
        anchor = "        /// Starts, updates, or commits one proportional resize drag from a circular corner handle.\n"
        text = text.replace(anchor, move_methods + anchor, 1)

        undo_methods = r'''        private func registerMoveUndo(original: PKDrawing, final: PKDrawing) {
            guard let manager = canvas?.undoManager else { return }
            manager.registerUndo(withTarget: self) { target in
                target.restoreDrawingForMove(original, reciprocal: final)
            }
            manager.setActionName("Move Selection")
        }

        private func restoreDrawingForMove(_ drawing: PKDrawing, reciprocal: PKDrawing) {
            guard let canvas else { return }
            loading = true
            canvas.drawing = drawing
            loading = false
            canvas.undoManager?.registerUndo(withTarget: self) { target in
                target.restoreDrawingForMove(reciprocal, reciprocal: drawing)
            }
            canvas.undoManager?.setActionName("Move Selection")
            refreshSelectionBounds()
            onDrawingChanged(drawing)
            onUndoManagerChanged(canvas.undoManager)
        }

'''
        anchor2 = "        /// Registers a custom resize as one Undo/Redo operation after the finger drag finishes.\n"
        text = text.replace(anchor2, undo_methods + anchor2, 1)
        return self._write_if_changed(path, original, text)
