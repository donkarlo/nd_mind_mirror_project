// Icon-only TikZ tool chooser with live thumbnails for all saved styles.

import SwiftUI

struct TikZToolStyleStripView: View {
    static let tools: [TikZCanvasTool] = [
        .rectangle, .ellipse, .triangle,
        .straightConnector, .curveConnector, .polylineConnector
    ]

    let tool: TikZCanvasTool
    let activeTool: TikZCanvasTool
    let presets: [TikZSavedStylePreset]
    let onChooseTool: (TikZCanvasTool) -> Void
    let onChoosePreset: (TikZSavedStylePreset) -> Void
    let onSave: (TikZCanvasTool) -> Void
    let onDelete: (UUID) -> Void

    var body: some View {
        HStack(spacing: 3) {
            Button {
                onChooseTool(tool)
            } label: {
                Image(systemName: symbolName)
                    .font(.system(size: 18))
                    .frame(width: 38, height: 38)
            }
            .buttonStyle(.bordered)
            .tint(activeTool == tool ? Color.accentColor : Color.secondary)
            .accessibilityLabel(tool.rawValue)

            ForEach(presets.filter { $0.tool == tool }) { preset in
                Button {
                    onChoosePreset(preset)
                } label: {
                    TikZStyleSampleView(
                        tool: preset.tool,
                        nodeStyle: preset.nodeStyle,
                        edgeStyle: preset.edgeStyle
                    )
                }
                .buttonStyle(.plain)
                .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 6))
                .overlay(RoundedRectangle(cornerRadius: 6)
                    .stroke(Color.secondary.opacity(0.35), lineWidth: 1))
                .contextMenu {
                    Button("Delete saved appearance", role: .destructive) {
                        onDelete(preset.id)
                    }
                }
                .accessibilityLabel("Saved \(tool.rawValue) appearance")
            }

            Button {
                onSave(tool)
            } label: {
                Image(systemName: "plus.circle")
                    .font(.system(size: 15))
                    .frame(width: 24, height: 34)
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Add current \(tool.rawValue) appearance")
        }
    }

    private var symbolName: String {
        switch tool {
        case .rectangle: return "rectangle"
        case .ellipse: return "circle"
        case .triangle: return "triangle"
        case .straightConnector: return "arrow.right"
        case .curveConnector: return "scribble.variable"
        case .polylineConnector: return "point.3.connected.trianglepath.dotted"
        case .select: return "cursorarrow"
        }
    }
}
