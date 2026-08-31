import PhotosUI
import SwiftUI

/// Owns toolbar-only UI state and saved-tool preset editing.
struct DrawingToolbarView: View {
    @ObservedObject var activeTool: ActiveDrawingToolController
    @ObservedObject var savedTools: SavedDrawingToolStore
    @ObservedObject var recentColors: RecentPencilColors
    @ObservedObject var editHistory: CanvasEditHistoryController
    @Binding var showMeasurementGrid: Bool
    @Binding var showMeasurementRulers: Bool
    @Binding var selectedPhotoItem: PhotosPickerItem?

    let onUndo: () -> Void
    let onRedo: () -> Void
    let onZoom100: () -> Void
    let onSetCanvas: (Double, Double) -> Void
    let onCustomCanvas: () -> Void
    let onClearDrawing: () -> Void
    let onDisconnect: () -> Void

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
                overlayButton($showMeasurementGrid, image: "square.grid.3x3", label: "Grid")
                overlayButton($showMeasurementRulers, image: "ruler", label: "Rulers")
                PhotosPicker(selection: $selectedPhotoItem, matching: .images) {
                    Image(systemName: "photo.badge.plus").frame(width: 30, height: 30)
                }
                .buttonStyle(.bordered)
                Button(action: onUndo) { Image(systemName: "arrow.uturn.backward") }
                    .disabled(activeTool.isPencilGestureActive)
                    .keyboardShortcut("z", modifiers: .command)
                Button(action: onRedo) { Image(systemName: "arrow.uturn.forward") }
                    .disabled(!editHistory.canRedo || activeTool.isPencilGestureActive)
                    .keyboardShortcut("z", modifiers: [.command, .shift])
                canvasMenu
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

    private func overlayButton(
        _ value: Binding<Bool>,
        image: String,
        label: String
    ) -> some View {
        Button { value.wrappedValue.toggle() } label: {
            Image(systemName: image)
                .frame(width: 32, height: 32)
                .background(value.wrappedValue ? Color.accentColor.opacity(0.18) : Color.clear)
                .overlay(RoundedRectangle(cornerRadius: 8).stroke(
                    value.wrappedValue ? Color.accentColor : Color.secondary.opacity(0.25),
                    lineWidth: value.wrappedValue ? 2 : 0.7
                ))
                .clipShape(RoundedRectangle(cornerRadius: 8))
        }
        .buttonStyle(.plain)
        .accessibilityLabel(label)
    }

    private var canvasMenu: some View {
        Menu {
            Button("100% zoom", action: onZoom100)
            Divider()
            Button("A4 portrait — 1240 × 1754") { onSetCanvas(1240, 1754) }
            Button("A4 landscape — 1754 × 1240") { onSetCanvas(1754, 1240) }
            Button("Square — 1600 × 1600") { onSetCanvas(1600, 1600) }
            Button("Custom canvas size…", action: onCustomCanvas)
            Divider()
            Button("Clear drawing", role: .destructive, action: onClearDrawing)
            Button("Disconnect", role: .destructive, action: onDisconnect)
        } label: {
            Image(systemName: "ellipsis.circle").frame(width: 30, height: 30)
        }
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
        // Never activate an arbitrary preset (the first one is usually black)
        // after deleting the current preset. A neutral non-drawing tool is safer.
        activeTool.select(kind: .lasso)
    }
}
