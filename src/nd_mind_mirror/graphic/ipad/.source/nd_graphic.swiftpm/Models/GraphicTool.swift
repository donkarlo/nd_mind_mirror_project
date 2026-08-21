// Defines the drawing and selection tools exposed by the native iPad companion.

import Foundation

/// Identifies the active PencilKit tool exposed by ND Graphic.
enum GraphicTool: String, CaseIterable, Identifiable {
    case pencil = "Pencil"
    case highlighter = "Highlighter"
    case eraser = "Eraser"
    case lasso = "Lasso"

    /// Returns the stable SwiftUI identity for the tool.
    var id: String { rawValue }

    /// Reports whether this tool exposes a selectable stroke color palette.
    var supportsColor: Bool { self == .pencil || self == .highlighter }

    /// Reports whether this tool exposes a stroke-width control.
    var supportsWidth: Bool { self == .pencil || self == .highlighter }

    /// Returns a stable lowercase key used for per-tool persisted preferences.
    var storageKey: String { rawValue.lowercased() }
}
