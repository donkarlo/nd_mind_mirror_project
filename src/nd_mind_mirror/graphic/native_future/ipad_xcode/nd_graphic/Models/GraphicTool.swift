import Foundation

enum GraphicTool: String, CaseIterable, Identifiable {
    case pencil = "Pencil"
    case highlighter = "Highlighter"
    case eraser = "Eraser"

    var id: String { rawValue }
}
