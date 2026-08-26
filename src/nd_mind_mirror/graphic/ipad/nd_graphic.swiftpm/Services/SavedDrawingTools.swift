import Foundation
import SwiftUI

/// One persistent toolbar drawing tool. There is intentionally no fixed slot count.
struct SavedDrawingTool: Codable, Hashable, Identifiable {
    let id: UUID
    var kindRawValue: String
    var colorHex: String
    var width: Double
    var opacity: Double

    var kind: GraphicTool {
        GraphicTool(rawValue: kindRawValue) ?? .pencil
    }
}

/// Stores an arbitrary number of persistent Pencil/Highlighter configurations.
@MainActor
final class SavedDrawingToolStore: ObservableObject {
    @Published private(set) var tools: [SavedDrawingTool]

    private let defaults = UserDefaults.standard
    private let storageKey = "graphic.saved.drawing.tools.v1"

    init() {
        if let data = defaults.data(forKey: storageKey),
           let decoded = try? JSONDecoder().decode([SavedDrawingTool].self, from: data),
           !decoded.isEmpty {
            tools = decoded.map(Self.canonicalized)
        } else {
            tools = Self.defaultTools
            persist()
        }
    }

    @discardableResult
    func add(kind: GraphicTool, color: Color, width: Double, opacity: Double) -> UUID? {
        guard kind.supportsColor && kind.supportsWidth else { return nil }
        let value = SavedDrawingTool(
            id: UUID(),
            kindRawValue: kind.rawValue,
            colorHex: Self.canonicalColorHex(color.hexRGB()),
            width: Self.canonicalWidth(width),
            opacity: Self.canonicalOpacity(opacity)
        )
        tools.append(value)
        persist()
        return value.id
    }

    func update(id: UUID, kind: GraphicTool, color: Color, width: Double, opacity: Double) {
        guard kind.supportsColor && kind.supportsWidth,
              let index = tools.firstIndex(where: { $0.id == id }) else { return }
        tools[index].kindRawValue = kind.rawValue
        tools[index].colorHex = Self.canonicalColorHex(color.hexRGB())
        tools[index].width = Self.canonicalWidth(width)
        tools[index].opacity = Self.canonicalOpacity(opacity)
        persist()
    }

    func remove(id: UUID) {
        tools.removeAll { $0.id == id }
        persist()
    }

    func moveLeft(id: UUID) {
        guard let index = tools.firstIndex(where: { $0.id == id }), index > 0 else { return }
        tools.swapAt(index, index - 1)
        persist()
    }

    func moveRight(id: UUID) {
        guard let index = tools.firstIndex(where: { $0.id == id }), index + 1 < tools.count else { return }
        tools.swapAt(index, index + 1)
        persist()
    }

    private func persist() {
        if let data = try? JSONEncoder().encode(tools) {
            defaults.set(data, forKey: storageKey)
        }
    }

    private static func canonicalized(_ value: SavedDrawingTool) -> SavedDrawingTool {
        SavedDrawingTool(
            id: value.id,
            kindRawValue: value.kind.supportsColor ? value.kind.rawValue : GraphicTool.pencil.rawValue,
            colorHex: canonicalColorHex(value.colorHex),
            width: canonicalWidth(value.width),
            opacity: canonicalOpacity(value.opacity)
        )
    }

    private static func canonicalColorHex(_ raw: String) -> String {
        var value = raw.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
        if value.hasPrefix("#") { value.removeFirst() }
        if value.count == 8 { value = String(value.prefix(6)) }
        guard value.count == 6, value.allSatisfy(\.isHexDigit) else { return "#000000" }
        return "#\(value)"
    }

    private static func canonicalWidth(_ raw: Double) -> Double {
        let finite = raw.isFinite ? raw : 1.0
        let bounded = min(max(finite, 0.5), 60.0)
        return (bounded * 2.0).rounded() / 2.0
    }

    private static func canonicalOpacity(_ raw: Double) -> Double {
        let finite = raw.isFinite ? raw : 1.0
        return (min(max(finite, 0.05), 1.0) * 20.0).rounded() / 20.0
    }

    private static let defaultTools: [SavedDrawingTool] = [
        SavedDrawingTool(id: UUID(), kindRawValue: GraphicTool.pencil.rawValue, colorHex: "#000000", width: 1.5, opacity: 1.0),
        SavedDrawingTool(id: UUID(), kindRawValue: GraphicTool.pencil.rawValue, colorHex: "#1971C2", width: 3.0, opacity: 1.0),
        SavedDrawingTool(id: UUID(), kindRawValue: GraphicTool.pencil.rawValue, colorHex: "#C92A2A", width: 5.0, opacity: 1.0),
        SavedDrawingTool(id: UUID(), kindRawValue: GraphicTool.highlighter.rawValue, colorHex: "#FFE066", width: 14.0, opacity: 0.35),
        SavedDrawingTool(id: UUID(), kindRawValue: GraphicTool.highlighter.rawValue, colorHex: "#8CE99A", width: 18.0, opacity: 0.45),
    ]
}
