// Persists independent recent/default color palettes for every color-capable iPad drawing tool.

import SwiftUI

/// Stores independent recent color histories so Pencil and Highlighter never overwrite each other's palette.
@MainActor
final class RecentPencilColors: ObservableObject {
    @Published private var colorsByTool: [String: [String]] = [:]

    private let maximumCount = 10
    private let defaultsByTool: [GraphicTool: [String]] = [
        .pencil: ["#111111", "#1D4ED8", "#B91C1C", "#15803D", "#7E22CE", "#9A3412", "#475569", "#FFFFFF"],
        .highlighter: ["#FFF176", "#A5D6A7", "#80DEEA", "#F8BBD0", "#FFCC80", "#CE93D8", "#90CAF9", "#E6EE9C"],
    ]

    /// Loads each tool's persisted color history and normalizes duplicate or invalid entries.
    init() {
        for tool in GraphicTool.allCases where tool.supportsColor {
            let stored = UserDefaults.standard.stringArray(forKey: defaultsKey(for: tool)) ?? []
            colorsByTool[tool.storageKey] = Self.uniqueNormalized(stored, maximumCount: maximumCount)
        }
    }

    /// Returns up to ten recent colors followed by tool-specific defaults that are not already present.
    func hexColors(for tool: GraphicTool) -> [String] {
        guard tool.supportsColor else { return [] }
        let recent = colorsByTool[tool.storageKey] ?? []
        let defaults = defaultsByTool[tool] ?? []
        return Self.uniqueNormalized(recent + defaults, maximumCount: maximumCount)
    }

    /// Returns only colors the user actually selected, newest first, with no default swatches mixed in.
    func recentHexColors(for tool: GraphicTool) -> [String] {
        guard tool.supportsColor else { return [] }
        return Array((colorsByTool[tool.storageKey] ?? []).prefix(maximumCount))
    }

    /// Returns the last ten user-selected colors for the toolbar matrix without adding synthetic defaults.
    func matrixHexColors(for tool: GraphicTool) -> [String] {
        recentHexColors(for: tool)
    }

    /// Returns the most appropriate current color for a tool, falling back to the caller's color if needed.
    func preferredHex(for tool: GraphicTool, fallback: String) -> String {
        hexColors(for: tool).first ?? Self.normalize(fallback)
    }

    /// Remembers a SwiftUI color in the history that belongs only to the selected drawing tool.
    func remember(_ color: Color, for tool: GraphicTool) {
        remember(hex: color.hexRGB(), for: tool)
    }

    /// Moves a hexadecimal color to the front of one tool's history and persists that history immediately.
    func remember(hex: String, for tool: GraphicTool) {
        guard tool.supportsColor else { return }
        let normalized = Self.normalize(hex)
        guard !normalized.isEmpty else { return }
        var values = colorsByTool[tool.storageKey] ?? []
        values.removeAll { $0.caseInsensitiveCompare(normalized) == .orderedSame }
        values.insert(normalized, at: 0)
        if values.count > maximumCount {
            values.removeLast(values.count - maximumCount)
        }
        colorsByTool[tool.storageKey] = values
        UserDefaults.standard.set(values, forKey: defaultsKey(for: tool))
    }

    /// Returns the UserDefaults key dedicated to one drawing tool's recent colors.
    private func defaultsKey(for tool: GraphicTool) -> String {
        "graphic.\(tool.storageKey).recentColors"
    }

    /// Normalizes a color list, removes duplicates in order, and limits the resulting palette length.
    private static func uniqueNormalized(_ rawValues: [String], maximumCount: Int) -> [String] {
        var seen = Set<String>()
        var result: [String] = []
        for raw in rawValues {
            let normalized = normalize(raw)
            guard !normalized.isEmpty else { continue }
            let key = normalized.uppercased()
            guard seen.insert(key).inserted else { continue }
            result.append(normalized)
            if result.count >= maximumCount { break }
        }
        return result
    }

    /// Converts a six-digit RGB value to canonical uppercase #RRGGBB form or returns an empty string.
    private static func normalize(_ raw: String) -> String {
        let cleaned = raw.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        guard cleaned.count == 6, UInt64(cleaned, radix: 16) != nil else { return "" }
        return "#" + cleaned.uppercased()
    }
}
