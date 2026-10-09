import SwiftUI

/// Compact, non-interactive indication of the tool currently editing the canvas.
struct ActiveToolHeaderIndicatorView: View {
    @ObservedObject var activeTool: ActiveDrawingToolController

    var body: some View {
        Image(systemName: symbolName)
            .font(.title3)
            .foregroundStyle(symbolColor)
            .frame(width: 30, height: 44)
            .accessibilityLabel("Selected tool: \(activeTool.kind.rawValue)")
    }

    private var symbolName: String {
        switch activeTool.kind {
        case .pencil: return "pencil"
        case .highlighter: return "highlighter"
        case .eraser: return activeTool.eraserMode == .whole ? "eraser.fill" : "eraser"
        case .lasso: return "lasso"
        }
    }

    private var symbolColor: Color {
        switch activeTool.kind {
        case .pencil, .highlighter:
            return activeTool.color.opacity(activeTool.opacity)
        case .eraser, .lasso:
            return .primary
        }
    }
}
