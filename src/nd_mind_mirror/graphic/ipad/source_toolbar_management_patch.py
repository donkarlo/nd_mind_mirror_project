'''Normalize saved drawing-tool controls and prevent destructive iPad image replacement.'''
from __future__ import annotations

from pathlib import Path


class IpadToolbarManagementPatch:
    def __init__(self, source_root: str | Path) -> None:
        self.source_root = Path(source_root).expanduser().resolve()

    def apply(self) -> bool:
        changed = False
        content_path = self.source_root / "Views" / "ContentView.swift"
        if content_path.is_file():
            original = content_path.read_text(encoding="utf-8")
            text = original
            text = self._remove_saved_tool_context_menu(text)
            text = self._ensure_saved_tool_management_menu(text)
            text = self._normalize_saved_tool_icons(text)
            text = self._remove_numeric_stroke_labels(text)
            text = self._repair_photo_import(text)
            text = self._remove_eager_insert_save(text)
            if text != original:
                content_path.write_text(text, encoding="utf-8")
                changed = True

        bridge_path = self.source_root / "Services" / "GraphicBridgeClient.swift"
        if bridge_path.is_file():
            original = bridge_path.read_text(encoding="utf-8")
            text = self._protect_background_during_autosave(original)
            if text != original:
                bridge_path.write_text(text, encoding="utf-8")
                changed = True

        return changed

    @staticmethod
    def _remove_saved_tool_context_menu(text: str) -> str:
        old_context = '''                    .contextMenu {
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
'''
        return text.replace(old_context, "")

    @staticmethod
    def _ensure_saved_tool_management_menu(text: str) -> str:
        if "ND_SAVED_TOOL_MANAGEMENT_MENU_V1" in text:
            return text
        anchor = '''                .help("Add another persistent drawing tool")

'''
        menu = '''                // ND_SAVED_TOOL_MANAGEMENT_MENU_V1
                Menu {
                    ForEach(savedTools.tools) { saved in
                        Menu("\\(saved.kind.rawValue) • \\(saved.colorHex)") {
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
                } label: {
                    Image(systemName: "slider.horizontal.3")
                        .frame(width: 28, height: 28)
                }
                .help("Manage saved drawing tools")

'''
        return text.replace(anchor, anchor + menu, 1)

    @staticmethod
    def _normalize_saved_tool_icons(text: str) -> str:
        old = '''                        HStack(spacing: 3) {
                            Image(systemName: saved.kind == .highlighter ? "highlighter" : "pencil")
                            Circle()
                                .fill(Color(hex: saved.colorHex))
                                .frame(width: 10, height: 10)
                            Text(String(format: "%.1f", saved.width))
                                .font(.caption2.monospacedDigit())
                            Text("\\(Int((saved.opacity * 100).rounded()))%")
                                .font(.caption2.monospacedDigit())
                        }
                        .padding(.horizontal, 4)
                        .frame(height: 28)
                        .background(
                            isSavedToolActive(saved) ? Color.accentColor.opacity(0.18) : Color.clear,
                            in: RoundedRectangle(cornerRadius: 7)
                        )
'''
        new = '''                        Image(systemName: saved.kind == .highlighter ? "highlighter" : "pencil")
                            .symbolRenderingMode(.monochrome)
                            .font(.system(
                                size: CGFloat(min(max(16.0 + saved.width * 0.22, 17.0), 29.0)),
                                weight: saved.width >= 40 ? .black
                                    : saved.width >= 24 ? .bold
                                    : saved.width >= 12 ? .semibold
                                    : saved.width >= 5 ? .medium
                                    : .regular
                            ))
                            .foregroundStyle(Color(hex: saved.colorHex).opacity(saved.opacity))
                            .frame(width: 34, height: 28)
                            .background(
                                isSavedToolActive(saved) ? Color.accentColor.opacity(0.18) : Color.clear,
                                in: RoundedRectangle(cornerRadius: 7)
                            )
'''
        return text.replace(old, new)

    @staticmethod
    def _remove_numeric_stroke_labels(text: str) -> str:
        width_label = '''                    Text(String(format: "%.1f", pencil.width))
                        .font(.caption2.monospacedDigit())
                        .frame(minWidth: 30, alignment: .trailing)
'''
        opacity_label = '''                    Text("\\(Int((toolOpacity * 100).rounded()))%")
                        .font(.caption2.monospacedDigit())
                        .frame(minWidth: 32, alignment: .trailing)
'''
        return text.replace(width_label, "").replace(opacity_label, "")

    @staticmethod
    def _replace_swift_function(text: str, signature: str, replacement: str) -> str:
        start = text.find(signature)
        if start < 0:
            return text
        brace = text.find("{", start)
        if brace < 0:
            return text

        depth = 0
        in_string = False
        escaped = False
        end = None
        for index in range(brace, len(text)):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end = index + 1
                    break
        if end is None:
            return text

        line_start = text.rfind("\n", 0, start) + 1
        comment_start = line_start
        previous_line_start = text.rfind("\n", 0, max(line_start - 1, 0)) + 1
        previous_line = text[previous_line_start:line_start].strip()
        if previous_line.startswith("///"):
            comment_start = previous_line_start

        return text[:comment_start] + replacement.rstrip() + "\n\n" + text[end:].lstrip("\n")

    @classmethod
    def _repair_photo_import(cls, text: str) -> str:
        replacement = '''    /// Inserts a selected Photos image as an editable object instead of replacing the document background.
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
    }'''
        return cls._replace_swift_function(
            text,
            "    private func importPhoto(_ item: PhotosPickerItem?)",
            replacement,
        )

    @staticmethod
    def _remove_eager_insert_save(text: str) -> str:
        eager_save = '''            if bridge.currentOperation == "insert" {
                DispatchQueue.main.async {
                    bridge.save(
                        drawing: localDrawing,
                        backgroundImage: backgroundImage,
                        logicalCanvasSize: logicalCanvasSize,
                        pencil: pencil
                    )
                }
            }
'''
        return text.replace(eager_save, "")

    @staticmethod
    def _protect_background_during_autosave(text: str) -> str:
        if "ND_SAFE_BACKGROUND_AUTOSAVE_V1" in text:
            return text

        old = '''        let imageObjects = CanvasImageObjectStore.load(documentIdentifier: path)
        guard let png = GraphicImageRenderer.pngData(
            drawing: drawing,
            backgroundImage: backgroundImage,
            imageObjects: imageObjects,
            logicalCanvasSize: logicalCanvasSize
        ) else {
'''
        new = '''        let imageObjects = CanvasImageObjectStore.load(documentIdentifier: path)

        // ND_SAFE_BACKGROUND_AUTOSAVE_V1
        // A SwiftUI state refresh can briefly pass nil while an existing update
        // document is being installed. For ordinary autosaves, fall back to the
        // background that arrived from Ubuntu so a transient nil can never
        // overwrite the real PNG with a white canvas. Explicit background
        // replacement/removal uses persistBackground=true and therefore keeps
        // the caller's value exactly.
        let effectiveBackgroundImage: UIImage?
        if persistBackground {
            effectiveBackgroundImage = backgroundImage
        } else {
            effectiveBackgroundImage =
                backgroundImage ?? GraphicDocumentStore.backgroundImage(from: document)
        }

        guard let png = GraphicImageRenderer.pngData(
            drawing: drawing,
            backgroundImage: effectiveBackgroundImage,
            imageObjects: imageObjects,
            logicalCanvasSize: logicalCanvasSize
        ) else {
'''
        text = text.replace(old, new, 1)

        old_persist = '''        if persistBackground {
            payload["background_image_base64"] = backgroundImage?.pngData()?.base64EncodedString() ?? ""
        }
'''
        new_persist = '''        if persistBackground {
            payload["background_image_base64"] =
                effectiveBackgroundImage?.pngData()?.base64EncodedString() ?? ""
        }
'''
        return text.replace(old_persist, new_persist, 1)
