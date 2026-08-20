import Foundation

/// Drawing modes intentionally map to clean TikZ primitives.
enum DrawingTool: String, CaseIterable, Identifiable {
    case freehand = "Freehand"
    case line = "Line"
    case arrow = "Arrow"
    case rectangle = "Rectangle node"
    case ellipse = "Ellipse node"
    case text = "Handwriting text"

    var id: String { rawValue }

    var symbolName: String {
        switch self {
        case .freehand: return "pencil.tip"
        case .line: return "line.diagonal"
        case .arrow: return "arrow.right"
        case .rectangle: return "rectangle"
        case .ellipse: return "circle"
        case .text: return "textformat.abc.dottedunderline"
        }
    }
}
