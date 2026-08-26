import Foundation
import SwiftUI

/// One recently edited graphic shown from the source/image identity menu.
struct RecentGraphicItem: Codable, Hashable, Identifiable {
    let path: String
    let label: String
    var id: String { path }
}

/// One recent pencil/highlighter combination.
struct RecentToolPreset: Codable, Hashable, Identifiable {
    let colorHex: String
    let width: Double
    var id: String { "\(colorHex.lowercased())|\(String(format: "%.2f", width))" }
}

/// Persists the ten most recent color/width combinations separately per inking tool.
@MainActor
final class RecentToolPresetStore: ObservableObject {
    @Published private(set) var revision = 0
    private let defaults = UserDefaults.standard
    private let limit = 10

    func presets(for tool: GraphicTool) -> [RecentToolPreset] {
        guard tool.supportsColor && tool.supportsWidth else { return [] }
        let key = "graphic.recent.tool.presets.\(tool.storageKey)"
        guard let data = defaults.data(forKey: key),
              let values = try? JSONDecoder().decode([RecentToolPreset].self, from: data) else {
            return []
        }
        return Array(values.prefix(limit))
    }

    func remember(color: Color, width: Double, for tool: GraphicTool) {
        remember(hex: color.hexRGB(), width: width, for: tool)
    }

    func remember(hex: String, width: Double, for tool: GraphicTool) {
        guard tool.supportsColor && tool.supportsWidth else { return }
        let normalized = hex.uppercased()
        let boundedWidth = max(width, 0.1)
        let value = RecentToolPreset(colorHex: normalized, width: boundedWidth)
        var values = presets(for: tool)
        values.removeAll {
            $0.colorHex.caseInsensitiveCompare(normalized) == .orderedSame
                && abs($0.width - boundedWidth) < 0.01
        }
        values.insert(value, at: 0)
        values = Array(values.prefix(limit))
        let key = "graphic.recent.tool.presets.\(tool.storageKey)"
        if let data = try? JSONEncoder().encode(values) {
            defaults.set(data, forKey: key)
            revision &+= 1
        }
    }
}

/// Persists the ten most recently edited bridge graphics.
enum RecentGraphicStore {
    private static let key = "graphic.recent.edited.graphics"
    private static let limit = 10

    static func load() -> [RecentGraphicItem] {
        guard let data = UserDefaults.standard.data(forKey: key),
              let values = try? JSONDecoder().decode([RecentGraphicItem].self, from: data) else {
            return []
        }
        return Array(values.prefix(limit))
    }

    @discardableResult
    static func remember(path: String, label: String) -> [RecentGraphicItem] {
        guard !path.isEmpty else { return load() }
        var values = load()
        values.removeAll { $0.path == path }
        values.insert(RecentGraphicItem(path: path, label: label), at: 0)
        values = Array(values.prefix(limit))
        if let data = try? JSONEncoder().encode(values) {
            UserDefaults.standard.set(data, forKey: key)
        }
        return values
    }
}
