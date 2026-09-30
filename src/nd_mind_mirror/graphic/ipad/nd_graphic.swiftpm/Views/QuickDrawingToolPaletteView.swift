import SwiftUI

/// A compact Apple Pencil palette placed near a double-tap location on the raster canvas.
struct QuickDrawingToolPaletteView: View {
    @ObservedObject var activeTool: ActiveDrawingToolController
    @ObservedObject var savedTools: SavedDrawingToolStore

    let anchor: CGPoint
    let onSelectSavedTool: (SavedDrawingTool) -> Void
    let onSelectLasso: () -> Void
    let onAddImage: () -> Void

    var body: some View {
        GeometryReader { proxy in
            palette
                .frame(
                    width: Layout.panelWidth,
                    height: Layout.panelHeight(itemCount: itemCount)
                )
                .position(
                    Layout.position(
                        anchor: anchor,
                        containerSize: proxy.size,
                        itemCount: itemCount
                    )
                )
        }
    }
    private var palette: some View {
        ScrollView(.vertical, showsIndicators: itemCount > Layout.maximumVisibleItems) {
            LazyVGrid(columns: Layout.columns, spacing: Layout.spacing) {
                ForEach(savedTools.tools) { savedTool in
                    savedToolButton(savedTool)
                }
                lassoButton
                addImageButton
            }
        }
        .frame(
            width: Layout.gridWidth,
            height: Layout.gridHeight(itemCount: itemCount)
        )
        .padding(Layout.padding)
        .background(
            .regularMaterial,
            in: RoundedRectangle(cornerRadius: 14, style: .continuous)
        )
        .overlay {
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .stroke(Color.secondary.opacity(0.28), lineWidth: 0.8)
        }
        .shadow(radius: 8, y: 3)
    }

    private var itemCount: Int {
        savedTools.tools.count + 2
    }
    private func savedToolButton(_ savedTool: SavedDrawingTool) -> some View {
        Button {
            onSelectSavedTool(savedTool)
        } label: {
            paletteCell(
                image: symbolName(for: savedTool),
                tint: tintColor(for: savedTool),
                isSelected: activeTool.isSelected(savedTool)
            )
        }
        .buttonStyle(.plain)
        .accessibilityLabel(accessibilityLabel(for: savedTool))
    }

    private var lassoButton: some View {
        Button(action: onSelectLasso) {
            paletteCell(
                image: "lasso",
                tint: .primary,
                isSelected: activeTool.kind == .lasso
                    && activeTool.selectedSavedToolID == nil
            )
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Lasso")
    }

    private var addImageButton: some View {
        Button(action: onAddImage) {
            paletteCell(
                image: "photo.badge.plus",
                tint: .primary,
                isSelected: false
            )
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Add image")
    }
    private func paletteCell(
        image: String,
        tint: Color,
        isSelected: Bool
    ) -> some View {
        Image(systemName: image)
            .font(.system(size: 22, weight: .medium))
            .foregroundStyle(tint)
            .frame(width: Layout.cellSize, height: Layout.cellSize)
            .background(
                isSelected
                    ? Color.accentColor.opacity(0.18)
                    : Color(uiColor: .secondarySystemBackground).opacity(0.72)
            )
            .overlay {
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .stroke(
                        isSelected ? Color.accentColor : Color.secondary.opacity(0.28),
                        lineWidth: isSelected ? 2.5 : 0.8
                    )
            }
            .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
            .contentShape(Rectangle())
    }

    private func symbolName(for tool: SavedDrawingTool) -> String {
        switch tool.kind {
        case .pencil: return "pencil"
        case .highlighter: return "highlighter"
        case .eraser:
            return tool.eraserMode == .whole ? "eraser.fill" : "eraser"
        case .lasso:
            return "lasso"
        }
    }

    private func tintColor(for tool: SavedDrawingTool) -> Color {
        tool.kind == .eraser ? .primary : Color(hex: tool.colorHex).opacity(tool.opacity)
    }

    private func accessibilityLabel(for tool: SavedDrawingTool) -> String {
        switch tool.kind {
        case .pencil:
            return "Pencil"
        case .highlighter:
            return "Highlighter"
        case .eraser:
            return "\(tool.eraserMode.title) eraser"
        case .lasso:
            return "Lasso"
        }
    }

    private enum Layout {
        static let columnCount = 4
        static let maximumVisibleRows = 4
        static let maximumVisibleItems = columnCount * maximumVisibleRows
        static let cellSize: CGFloat = 48
        static let spacing: CGFloat = 6
        static let padding: CGFloat = 8
        static let edgeMargin: CGFloat = 8
        static let pencilGap: CGFloat = 16

        static let columns = Array(
            repeating: GridItem(.fixed(cellSize), spacing: spacing),
            count: columnCount
        )

        static var gridWidth: CGFloat {
            CGFloat(columnCount) * cellSize
                + CGFloat(columnCount - 1) * spacing
        }

        static var panelWidth: CGFloat {
            gridWidth + 2 * padding
        }

        static func visibleRows(itemCount: Int) -> Int {
            let requiredRows = max(1, (itemCount + columnCount - 1) / columnCount)
            return min(requiredRows, maximumVisibleRows)
        }

        static func gridHeight(itemCount: Int) -> CGFloat {
            let rows = visibleRows(itemCount: itemCount)
            return CGFloat(rows) * cellSize + CGFloat(max(rows - 1, 0)) * spacing
        }

        static func panelHeight(itemCount: Int) -> CGFloat {
            gridHeight(itemCount: itemCount) + 2 * padding
        }

        static func position(
            anchor: CGPoint,
            containerSize: CGSize,
            itemCount: Int
        ) -> CGPoint {
            let panelSize = CGSize(
                width: panelWidth,
                height: panelHeight(itemCount: itemCount)
            )
            let halfWidth = panelSize.width / 2
            let halfHeight = panelSize.height / 2

            let minimumX = halfWidth + edgeMargin
            let maximumX = max(minimumX, containerSize.width - halfWidth - edgeMargin)
            let x = min(max(anchor.x, minimumX), maximumX)

            let minimumY = halfHeight + edgeMargin
            let maximumY = max(minimumY, containerSize.height - halfHeight - edgeMargin)
            let preferredAboveY = anchor.y - pencilGap - halfHeight
            let y = min(max(preferredAboveY, minimumY), maximumY)

            return CGPoint(x: x, y: y)
        }
    }
}
