// Double-tap TikZ tool palette anchored to the Pencil's canvas contact.

import SwiftUI

struct TikZPencilToolPaletteView: View {
    let anchor: CGPoint
    let activeTool: TikZCanvasTool
    let presets: [TikZSavedStylePreset]
    let onChooseTool: (TikZCanvasTool) -> Void
    let onChoosePreset: (TikZSavedStylePreset) -> Void
    let onSave: (TikZCanvasTool) -> Void
    let onDelete: (UUID) -> Void
    let onDismiss: () -> Void

    private let width: CGFloat = 292
    private let height: CGFloat = 284

    var body: some View {
        GeometryReader { proxy in
            ScrollView(.vertical, showsIndicators: true) {
                VStack(alignment: .leading, spacing: 5) {
                    HStack {
                        Button(action: onDismiss) {
                            Image(systemName: "xmark")
                                .font(.system(size: 15, weight: .semibold))
                        }
                        .buttonStyle(.plain)
                        Spacer()
                    }
                    ForEach(TikZToolStyleStripView.tools, id: \.self) { tool in
                        ScrollView(.horizontal, showsIndicators: false) {
                            TikZToolStyleStripView(
                                tool: tool,
                                activeTool: activeTool,
                                presets: presets,
                                onChooseTool: onChooseTool,
                                onChoosePreset: onChoosePreset,
                                onSave: onSave,
                                onDelete: onDelete
                            )
                        }
                    }
                }
                .padding(8)
            }
            .frame(width: width, height: height)
            .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 15))
            .overlay(RoundedRectangle(cornerRadius: 15)
                .stroke(Color.secondary.opacity(0.25)))
            .shadow(radius: 8, y: 3)
            .position(paletteCenter(in: proxy.size))
        }
    }

    private func paletteCenter(in size: CGSize) -> CGPoint {
        // Keep the palette within the visible canvas while placing it above
        // the Pencil when there is room, otherwise below the contact point.
        let halfWidth = width / 2
        let halfHeight = height / 2
        let gap: CGFloat = 12
        let x = min(max(anchor.x, halfWidth), max(halfWidth, size.width - halfWidth))
        let above = anchor.y - halfHeight - gap
        let below = anchor.y + halfHeight + gap
        let y = above >= halfHeight ? above : below
        let clampedY = min(max(y, halfHeight), max(halfHeight, size.height - halfHeight))
        return CGPoint(x: x, y: clampedY)
    }
}
