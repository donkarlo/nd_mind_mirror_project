"""Dynamic ContentView toolbar/image-object source normalization."""
from __future__ import annotations
from pathlib import Path
import re

class IpadDynamicContentPatch:
    def __init__(self, source_root: str | Path) -> None:
        self.source_root = Path(source_root).expanduser().resolve()

    def apply(self) -> bool:
        changed = self._repair_content_view()
        changed |= self._patch_dynamic_content_view()
        return changed

    @staticmethod
    def _write_if_changed(path: Path, original: str, updated: str) -> bool:
        if updated == original:
            return False
        path.write_text(updated, encoding="utf-8")
        return True

    def _repair_content_view(self) -> bool:
        path = self.source_root / "Views" / "ContentView.swift"
        if not path.is_file():
            return False
        original = path.read_text(encoding="utf-8")
        text = original

        for name in (
            "fixedPresets",
            "recentPresets",
            "recentGraphics",
            "rememberedCanvasWidth",
            "rememberedCanvasHeight",
            "showMeasurementGrid",
            "showMeasurementRulers",
        ):
            text = self._dedupe_property(text, name)

        text = re.sub(
            r'\n    private var recentToolPresetPopover: some View \{.*?\n    \}\n(?=\n    (?:///|@ViewBuilder|private|var ))',
            "\n",
            text,
            count=1,
            flags=re.S,
        )
        text = re.sub(r'(?m)^    @StateObject private var recentPresets = RecentToolPresetStore\(\)\n', "", text)
        text = re.sub(r'(?m)^    @State private var showToolPresets = false\n', "", text)

        if "ND_CONTENT_BUNDLE_VERSION_V1" not in text:
            version_property = '''    // ND_CONTENT_BUNDLE_VERSION_V1
    private var displayVersion: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "unknown"
    }

'''
            anchor = "    /// Selects the connection, waiting, or drawing screen"
            index = text.find(anchor)
            if index >= 0:
                text = text[:index] + version_property + text[index:]
        text = re.sub(
            r'Text\("ND Graphic v[0-9]+(?:\.[0-9]+)+"\)',
            'Text("ND Graphic v\\(displayVersion)")',
            text,
        )
        return self._write_if_changed(path, original, text)

    def _patch_dynamic_content_view(self) -> bool:
        path = self.source_root / "Views" / "ContentView.swift"
        if not path.is_file():
            return False
        original = path.read_text(encoding="utf-8")
        text = original

        text = re.sub(r'(?m)^    @StateObject private var fixedPresets = FixedToolPresetStore\(\)\n', "", text)
        text = re.sub(r'(?m)^    @StateObject private var recentPresets = RecentToolPresetStore\(\)\n', "", text)
        text = re.sub(r'(?m)^    @State private var showToolPresets = false\n', "", text)

        if "ND_DYNAMIC_TOOLBAR_STATE_V1" not in text:
            state = '''    // ND_DYNAMIC_TOOLBAR_STATE_V1
    @StateObject private var savedTools = SavedDrawingToolStore()
    @StateObject private var imageObjectManager = CanvasImageObjectManager()
    @AppStorage("graphic.stroke.lastOpacity") private var toolOpacity: Double = 1.0
'''
            anchor = "    @StateObject private var recentColors = RecentPencilColors()\n"
            text = text.replace(anchor, anchor + state, 1)

        dynamic_toolbar = r'''                // ND_DYNAMIC_SAVED_TOOLS_V1
                ForEach(savedTools.tools) { saved in
                    Button {
                        applySavedTool(saved)
                    } label: {
                        HStack(spacing: 3) {
                            Image(systemName: saved.kind == .highlighter ? "highlighter" : "pencil")
                            Circle()
                                .fill(Color(hex: saved.colorHex))
                                .frame(width: 10, height: 10)
                            Text(String(format: "%.1f", saved.width))
                                .font(.caption2.monospacedDigit())
                            Text("\(Int((saved.opacity * 100).rounded()))%")
                                .font(.caption2.monospacedDigit())
                        }
                        .padding(.horizontal, 4)
                        .frame(height: 28)
                        .background(
                            isSavedToolActive(saved) ? Color.accentColor.opacity(0.18) : Color.clear,
                            in: RoundedRectangle(cornerRadius: 7)
                        )
                    }
                    .buttonStyle(.plain)
                    .contextMenu {
                        Button("Update from current settings") {
                            savedTools.update(
                                id: saved.id,
                                kind: tool.supportsColor ? tool : saved.kind,
                                color: pencil.color,
                                width: pencil.width,
                                opacity: toolOpacity
                            )
                        }
                        Button("Move left") { savedTools.moveLeft(id: saved.id) }
                        Button("Move right") { savedTools.moveRight(id: saved.id) }
                        Divider()
                        Button("Delete saved tool", role: .destructive) {
                            savedTools.remove(id: saved.id)
                        }
                    }
                }

                Menu {
                    if tool.supportsColor && tool.supportsWidth {
                        Button("Add current settings") {
                            _ = savedTools.add(
                                kind: tool,
                                color: pencil.color,
                                width: pencil.width,
                                opacity: toolOpacity
                            )
                        }
                    }
                    Button("Add Pencil with current settings") {
                        _ = savedTools.add(
                            kind: .pencil,
                            color: pencil.color,
                            width: pencil.width,
                            opacity: toolOpacity
                        )
                    }
                    Button("Add Highlighter with current settings") {
                        _ = savedTools.add(
                            kind: .highlighter,
                            color: pencil.color,
                            width: pencil.width,
                            opacity: toolOpacity
                        )
                    }
                } label: {
                    Image(systemName: "plus.circle")
                        .frame(width: 28, height: 28)
                }
                .help("Add another persistent drawing tool")

                toolButton(.eraser, systemImage: "eraser")
                toolButton(.lasso, systemImage: "lasso")

'''
        fixed_pattern = re.compile(
            r'                // ND_FIXED_TOOL_PRESETS_V1\n.*?(?=                if tool\.supportsColor \{)',
            re.S,
        )
        match = fixed_pattern.search(text)
        if match is not None:
            text = text[:match.start()] + dynamic_toolbar + text[match.end():]
        else:
            long_pattern = re.compile(
                r'                // ND_TOOL_BUTTONS_LONG_PRESS_V1\n.*?                \.popover\(isPresented: \$showToolPresets, arrowEdge: \.top\) \{\n                    recentToolPresetPopover\n                \}\n\n',
                re.S,
            )
            match = long_pattern.search(text)
            if match is not None:
                text = text[:match.start()] + dynamic_toolbar + text[match.end():]

        text = text.replace(
            '''        .onChange(of: tool) { oldTool, newTool in
            switchToolColor(from: oldTool, to: newTool)
            showRecentColors = false
        }
''',
            '''        .onChange(of: tool) { _, _ in
            showRecentColors = false
        }
''',
        )
        text = re.sub(
            r'        \.onChange\(of: pencil\.width\) \{ _, newWidth in\n            if tool\.supportsWidth \{\n.*?\n            \}\n        \}\n',
            "",
            text,
            flags=re.S,
        )

        if "ND_IMAGE_OBJECT_DOCUMENT_LOAD_V1" not in text:
            anchor = "            backgroundImage = GraphicDocumentStore.backgroundImage(from: bridge.document)\n"
            insertion = '''            // ND_IMAGE_OBJECT_DOCUMENT_LOAD_V1
            if let path = bridge.selectedPath {
                if bridge.currentOperation == "insert" {
                    imageObjectManager.beginNewDocument(documentIdentifier: path)
                } else {
                    imageObjectManager.load(
                        documentIdentifier: path,
                        remoteObjects: bridge.document?.imageObjects
                    )
                }
            } else {
                imageObjectManager.load(documentIdentifier: "")
            }
'''
            text = text.replace(anchor, anchor + insertion, 1)

        if "ND_IMAGE_OBJECT_AUTOSAVE_V1" not in text:
            anchor = '''        .onChange(of: tool) { _, _ in
            showRecentColors = false
        }
'''
            addition = '''        // ND_IMAGE_OBJECT_AUTOSAVE_V1
        .onChange(of: imageObjectManager.editRevision) { _, _ in
            scheduleAutosave(drawing: localDrawing, immediate: true)
        }
'''
            text = text.replace(anchor, anchor + addition, 1)

        if "imageObjects: imageObjectManager.objects" not in text:
            text = text.replace(
                "                width: pencil.width,\n                logicalCanvasSize: logicalCanvasSize,\n",
                "                width: pencil.width,\n                opacity: toolOpacity,\n                imageObjects: imageObjectManager.objects,\n                selectedImageObjectID: imageObjectManager.selectedID,\n                logicalCanvasSize: logicalCanvasSize,\n",
                1,
            )
        text = text.replace(
            "                onUndoManagerChanged: { manager in canvasUndoManager = manager },\n                onZoomChanged: { scale in zoomScale = scale }\n",
            '''                onUndoManagerChanged: { manager in
                    canvasUndoManager = manager
                    imageObjectManager.undoManager = manager
                },
                onZoomChanged: { scale in zoomScale = scale },
                onImageObjectSelectionChanged: { id in
                    imageObjectManager.setSelected(id)
                },
                onImageObjectsCommitted: { objects, selectedID, actionName in
                    imageObjectManager.commitFromCanvas(
                        objects,
                        selectedID: selectedID,
                        actionName: actionName
                    )
                }
''',
            1,
        )

        width_pattern = re.compile(
            r'                if tool\.supportsWidth \{\n                    CompactThicknessSlider\(value: \$pencil\.width, range: 1\.\.\.24, step: 0\.5\)\n.*?                \}\n\n(?=                PhotosPicker)',
            re.S,
        )
        width_replacement = r'''                if tool.supportsWidth {
                    CompactThicknessSlider(value: $pencil.width, range: 0.5...60, step: 0.5)
                        .frame(width: 108, height: 24)
                    Text(String(format: "%.1f", pencil.width))
                        .font(.caption2.monospacedDigit())
                        .frame(minWidth: 30, alignment: .trailing)
                }

                if tool.supportsColor {
                    Slider(value: $toolOpacity, in: 0.05...1.0, step: 0.05)
                        .frame(width: 88)
                        .help("Opacity")
                    Text("\(Int((toolOpacity * 100).rounded()))%")
                        .font(.caption2.monospacedDigit())
                        .frame(minWidth: 32, alignment: .trailing)
                }

'''
        match = width_pattern.search(text)
        if match is not None:
            text = text[:match.start()] + width_replacement + text[match.end():]

        if "ND_IMAGE_DELETE_BUTTON_V1" not in text:
            anchor = "                .onChange(of: selectedPhotoItem) { _, item in importPhoto(item) }\n\n"
            insertion = '''                // ND_IMAGE_DELETE_BUTTON_V1
                Button {
                    imageObjectManager.deleteSelected()
                } label: {
                    Image(systemName: "trash")
                }
                .disabled(imageObjectManager.selectedID == nil)
                .help("Delete selected image object")

'''
            text = text.replace(anchor, anchor + insertion, 1)

        import_pattern = re.compile(
            r'    /// Loads a selected Photos image as the canvas background.*?(?=    /// Returns the clamped logical canvas size used for rendering and persistence\.)',
            re.S,
        )
        import_replacement = '''    /// Inserts a Photos image as an editable object with proportional size and Undo/Redo.
    private func importPhoto(_ item: PhotosPickerItem?) {
        guard let item else { return }
        Task {
            guard let data = try? await item.loadTransferable(type: Data.self),
                  let image = UIImage(data: data) else {
                await MainActor.run { bridge.status = "Could not load the selected photo" }
                return
            }
            await MainActor.run {
                selectedPhotoItem = nil
                if imageObjectManager.insert(image: image, canvasSize: logicalCanvasSize) != nil {
                    tool = .lasso
                    bridge.status = "Image inserted — use Lasso/finger to move or resize"
                } else {
                    bridge.status = "Could not insert the selected photo"
                }
            }
        }
    }

'''
        match = import_pattern.search(text)
        if match is not None:
            text = text[:match.start()] + import_replacement + text[match.end():]

        text = re.sub(
            r'    /// Applies one of the four permanent color/thickness slots\..*?\n    \}\n\n',
            "",
            text,
            count=1,
            flags=re.S,
        )
        text = re.sub(
            r'    private func applyFixedPreset\(_ preset: FixedToolPreset\) \{.*?\n    \}\n\n',
            "",
            text,
            count=1,
            flags=re.S,
        )
        if "private func applySavedTool(" not in text:
            helpers = '''    /// Applies one persistent toolbar drawing tool.
    private func applySavedTool(_ saved: SavedDrawingTool) {
        tool = saved.kind
        pencil.color = Color(hex: saved.colorHex)
        pencil.width = saved.width
        toolOpacity = saved.opacity
        recentColors.remember(hex: saved.colorHex, for: saved.kind)
    }

    private func isSavedToolActive(_ saved: SavedDrawingTool) -> Bool {
        guard tool == saved.kind else { return false }
        let sameColor = pencil.color.hexRGB().uppercased() == saved.colorHex.uppercased()
        return sameColor
            && abs(pencil.width - saved.width) < 0.01
            && abs(toolOpacity - saved.opacity) < 0.01
    }

'''
            anchor = "    /// Binds the color picker to the current tool"
            index = text.find(anchor)
            if index >= 0:
                text = text[:index] + helpers + text[index:]

        return self._write_if_changed(path, original, text)

    @staticmethod
    def _dedupe_property(text: str, property_name: str) -> str:
        pattern = re.compile(
            rf'(?m)^    @[^\n]*\b(?:private\s+)?var\s+{re.escape(property_name)}\b[^\n]*\n'
        )
        matches = list(pattern.finditer(text))
        if len(matches) <= 1:
            return text
        for match in reversed(matches[1:]):
            text = text[:match.start()] + text[match.end():]
        return text
