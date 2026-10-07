import SwiftUI

/// Settings section shared by the persistent toolbar and the Pencil double-tap palette.
struct DrawingToolbarSettingsSectionView: View {
    @ObservedObject var toolbarSettings: DrawingToolbarSettingsStore
    @ObservedObject var savedTools: SavedDrawingToolStore

    var body: some View {
        Section("Drawing toolbar") {
            Toggle(
                "Show drawing toolbar",
                isOn: Binding(
                    get: { toolbarSettings.isToolbarVisible },
                    set: { toolbarSettings.setToolbarVisible($0) }
                )
            )

            Text(
                "Tap Edit, then drag the reorder handles. The same order is used "
                + "by the top toolbar and the Apple Pencil double-tap palette."
            )
            .font(.footnote)
            .foregroundStyle(.secondary)

            ForEach(toolbarSettings.items(for: savedTools.tools)) { item in
                itemRow(item)
            }
            .onMove { offsets, destination in
                toolbarSettings.move(
                    fromOffsets: offsets,
                    toOffset: destination,
                    savedTools: savedTools.tools
                )
            }
        }
    }

    @ViewBuilder
    private func itemRow(_ item: DrawingToolbarItem) -> some View {
        switch item {
        case .savedTool(let id):
            if let tool = savedTools.tools.first(where: { $0.id == id }) {
                HStack(spacing: 12) {
                    Image(systemName: symbolName(for: tool))
                        .foregroundStyle(tintColor(for: tool))
                        .frame(width: 24)
                    Text(title(for: tool))
                }
            }
        case .lasso:
            Label("Lasso", systemImage: "lasso")
        case .addImage:
            Label("Import image", systemImage: "photo.badge.plus")
        }
    }

    private func title(for tool: SavedDrawingTool) -> String {
        switch tool.kind {
        case .pencil:
            return "Pencil · \(formattedWidth(tool.width))"
        case .highlighter:
            return "Highlighter · \(formattedWidth(tool.width))"
        case .eraser:
            return "\(tool.eraserMode.title) Eraser · \(formattedWidth(tool.width))"
        case .lasso:
            return "Lasso"
        }
    }

    private func formattedWidth(_ width: Double) -> String {
        width.formatted(.number.precision(.fractionLength(0...1))) + " px"
    }

    private func symbolName(for tool: SavedDrawingTool) -> String {
        switch tool.kind {
        case .pencil:
            return "pencil"
        case .highlighter:
            return "highlighter"
        case .eraser:
            return tool.eraserMode == .whole ? "eraser.fill" : "eraser"
        case .lasso:
            return "lasso"
        }
    }

    private func tintColor(for tool: SavedDrawingTool) -> Color {
        tool.kind == .eraser
            ? .primary
            : Color(hex: tool.colorHex).opacity(tool.opacity)
    }
}
