import SwiftUI

/// Shows the active drawing tool beside the Pencil's first contact point.
struct PencilContactToolPreviewView: View {
    let tool: GraphicTool
    let color: Color
    let opacity: Double
    let eraserMode: EraserMode
    let anchor: CGPoint

    var body: some View {
        GeometryReader { proxy in
            Image(systemName: symbolName)
            .font(.system(size: 19, weight: .semibold))
            .foregroundStyle(iconColor)
            .frame(width: 34, height: 34)
            .background(.regularMaterial, in: Circle())
            .overlay {
                Circle().stroke(Color.secondary.opacity(0.28), lineWidth: 0.8)
            }
            .shadow(radius: 3, y: 1)
            .position(
                x: min(max(anchor.x + 34, 21), max(proxy.size.width - 21, 21)),
                y: min(max(anchor.y - 38, 21), max(proxy.size.height - 21, 21))
            )
            .allowsHitTesting(false)
        }
        .allowsHitTesting(false)
    }

    private var symbolName: String {
        switch tool {
        case .pencil: return "pencil"
        case .highlighter: return "highlighter"
        case .eraser: return eraserMode == .whole ? "eraser.fill" : "eraser"
        case .lasso: return "lasso"
        }
    }

    private var iconColor: Color {
        switch tool {
        case .pencil, .highlighter:
            return color.opacity(opacity)
        case .eraser, .lasso:
            return .primary
        }
    }
}
