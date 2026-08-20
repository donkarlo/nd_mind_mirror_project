import Foundation

enum GraphicTool: String, CaseIterable, Identifiable {
    case pencil = "Pencil"
    case eraser = "Eraser"

    var id: String { rawValue }
}
