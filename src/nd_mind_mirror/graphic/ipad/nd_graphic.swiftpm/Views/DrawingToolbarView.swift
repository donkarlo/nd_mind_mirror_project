import PhotosUI
import SwiftUI

/// Owns toolbar-only UI state and saved-tool preset editing.
struct DrawingToolbarView: View {
    @ObservedObject var activeTool: ActiveDrawingToolController
    @ObservedObject var savedTools: SavedDrawingToolStore
    @ObservedObject var recentColors: RecentPencilColors
    @Binding var selectedPhotoItem: PhotosPickerItem?

    @State private var editingToolID: UUID?
    @State private var editorColor: Color = .black
    @State private var editorWidth: Double = 1.5
    @State private var editorOpacity: Double = 1
    @State private var editorEraserMode: EraserMode = .whole

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 7) {
                ForEach(savedTools.tools) { saved in
                    savedToolButton(saved)
                }
                systemToolButton(.lasso, image: "lasso")
                PhotosPicker(selection: $selectedPhotoItem, matching: .images) {
                    Image(systemName: "photo.badge.plus").frame(width: 30, height: 30)
                }
                .buttonStyle(.bordered)
            }
            .controlSize(.small)
            .padding(.horizontal, 8)
            .padding(.vertical, 6)
        }
        .background(.bar)
    }

    private func savedToolButton(_ saved: SavedDrawingTool) -> some View {
        SavedDrawingToolControl(
            savedTool: saved,
            isActive: activeTool.isSelected(saved),
            onSelect: { select(saved) },
            onEdit: { openEditor(saved) }
        )
        .frame(width: 42, height: 36)
        .popover(
            isPresented: Binding(
                get: { editingToolID == saved.id },
                set: { if !$0 && editingToolID == saved.id { editingToolID = nil } }
            )
        ) {
            DrawingToolEditorView(
                savedTool: saved,
                color: $editorColor,
                width: $editorWidth,
                opacity: $editorOpacity,
                eraserMode: $editorEraserMode,
                recentColorHexes: recentColors.hexColors(for: saved.kind),
                onRecentColor: { recentColors.remember(hex: $0, for: saved.kind) },
                onAdd: { addTool(after: saved) },
                onChange: { changeTool(saved) },
                onDelete: { deleteTool(saved) },
                onDone: { editingToolID = nil }
            )
        }
    }

    private func systemToolButton(_ kind: GraphicTool, image: String) -> some View {
        let selected = activeTool.kind == kind && activeTool.selectedSavedToolID == nil
        return Button {
            activeTool.select(kind: kind)
        } label: {
            Image(systemName: image)
                .frame(width: 32, height: 32)
                .background(selected ? Color.accentColor.opacity(0.18) : Color.clear)
                .overlay(RoundedRectangle(cornerRadius: 8).stroke(
                    selected ? Color.accentColor : Color.secondary.opacity(0.25),
                    lineWidth: selected ? 2.5 : 0.7
                ))
                .clipShape(RoundedRectangle(cornerRadius: 8))
        }
        .buttonStyle(.plain)
    }

    private func select(_ saved: SavedDrawingTool) {
        activeTool.select(savedTool: saved)
        if saved.kind.supportsColor {
            recentColors.remember(hex: saved.colorHex, for: saved.kind)
        }
    }

    private func openEditor(_ saved: SavedDrawingTool) {
        select(saved)
        editorColor = Color(hex: saved.colorHex)
        editorWidth = saved.width
        editorOpacity = saved.opacity
        editorEraserMode = saved.eraserMode
        editingToolID = saved.id
    }

    private func addTool(after saved: SavedDrawingTool) {
        let newID: UUID?
        if saved.kind == .eraser {
            newID = savedTools.addEraser(
                mode: editorEraserMode,
                width: editorWidth,
                after: saved.id
            )
        } else {
            newID = savedTools.add(
                kind: saved.kind,
                color: editorColor,
                width: editorWidth,
                opacity: editorOpacity,
                after: saved.id
            )
        }
        guard let newID,
              let created = savedTools.tools.first(where: { $0.id == newID }) else { return }
        openEditor(created)
    }

    private func changeTool(_ saved: SavedDrawingTool) {
        if saved.kind == .eraser {
            savedTools.updateEraser(
                id: saved.id,
                mode: editorEraserMode,
                width: editorWidth
            )
        } else {
            savedTools.update(
                id: saved.id,
                kind: saved.kind,
                color: editorColor,
                width: editorWidth,
                opacity: editorOpacity
            )
        }
        if let updated = savedTools.tools.first(where: { $0.id == saved.id }) {
            select(updated)
        }
    }

    private func deleteTool(_ saved: SavedDrawingTool) {
        let wasActive = activeTool.selectedSavedToolID == saved.id
        savedTools.remove(id: saved.id)
        editingToolID = nil
        guard wasActive else { return }
        activeTool.select(kind: .lasso)
    }
}

