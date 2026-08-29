import Foundation
import SwiftUI

/// One persistent toolbar drawing tool. Pencil, marker, and eraser presets share the same ordering model.
struct SavedDrawingTool: Codable, Hashable, Identifiable {
    let id: UUID
    var kindRawValue: String
    var colorHex: String
    var width: Double
    var opacity: Double
    var eraserModeRawValue: String?

    var kind: GraphicTool {
        GraphicTool(rawValue: kindRawValue) ?? .pencil
    }

    var eraserMode: EraserMode {
        guard kind == .eraser else { return .whole }
        return EraserMode(rawValue: eraserModeRawValue ?? "") ?? .whole
    }
}

/// Stores an arbitrary number of persistent Pencil, Highlighter, and Eraser configurations.
@MainActor
final class SavedDrawingToolStore: ObservableObject {
    @Published private(set) var tools: [SavedDrawingTool]

    private let defaults = UserDefaults.standard
    private let storageKey = "graphic.saved.drawing.tools.v2"
    private let legacyStorageKey = "graphic.saved.drawing.tools.v1"

    init() {
        if let data = defaults.data(forKey: storageKey),
           let decoded = try? JSONDecoder().decode([SavedDrawingTool].self, from: data),
           !decoded.isEmpty {
            tools = decoded.map(Self.canonicalized)
            return
        }

        if let legacyData = defaults.data(forKey: legacyStorageKey),
           let legacy = try? JSONDecoder().decode([SavedDrawingTool].self, from: legacyData),
           !legacy.isEmpty {
            var migrated = legacy.map(Self.canonicalized)
            if !migrated.contains(where: { $0.kind == .eraser }) {
                migrated.append(contentsOf: Self.defaultErasers)
            }
            tools = migrated
            persist()
            return
        }

        tools = Self.defaultTools
        persist()
    }

    @discardableResult
    func add(
        kind: GraphicTool,
        color: Color,
        width: Double,
        opacity: Double,
        after afterID: UUID? = nil
    ) -> UUID? {
        guard kind == .pencil || kind == .highlighter else { return nil }
        let value = SavedDrawingTool(
            id: UUID(),
            kindRawValue: kind.rawValue,
            colorHex: Self.canonicalColorHex(color.hexRGB()),
            width: Self.canonicalInkWidth(width),
            opacity: Self.canonicalOpacity(opacity),
            eraserModeRawValue: nil
        )
        insert(value, after: afterID)
        return value.id
    }

    @discardableResult
    func addEraser(
        mode: EraserMode,
        width: Double,
        after afterID: UUID? = nil
    ) -> UUID {
        let value = SavedDrawingTool(
            id: UUID(),
            kindRawValue: GraphicTool.eraser.rawValue,
            colorHex: "#000000",
            width: Self.canonicalEraserWidth(width),
            opacity: 1.0,
            eraserModeRawValue: mode.rawValue
        )
        insert(value, after: afterID)
        return value.id
    }

    func update(id: UUID, kind: GraphicTool, color: Color, width: Double, opacity: Double) {
        guard kind == .pencil || kind == .highlighter,
              let index = tools.firstIndex(where: { $0.id == id }) else { return }
        tools[index].kindRawValue = kind.rawValue
        tools[index].colorHex = Self.canonicalColorHex(color.hexRGB())
        tools[index].width = Self.canonicalInkWidth(width)
        tools[index].opacity = Self.canonicalOpacity(opacity)
        tools[index].eraserModeRawValue = nil
        persist()
    }

    func updateEraser(id: UUID, mode: EraserMode, width: Double) {
        guard let index = tools.firstIndex(where: { $0.id == id }) else { return }
        tools[index].kindRawValue = GraphicTool.eraser.rawValue
        tools[index].colorHex = "#000000"
        tools[index].width = Self.canonicalEraserWidth(width)
        tools[index].opacity = 1.0
        tools[index].eraserModeRawValue = mode.rawValue
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

    private func insert(_ value: SavedDrawingTool, after afterID: UUID?) {
        if let afterID,
           let index = tools.firstIndex(where: { $0.id == afterID }) {
            tools.insert(value, at: index + 1)
        } else {
            tools.append(value)
        }
        persist()
    }

    private func persist() {
        if let data = try? JSONEncoder().encode(tools) {
            defaults.set(data, forKey: storageKey)
        }
    }

    private static func canonicalized(_ value: SavedDrawingTool) -> SavedDrawingTool {
        switch value.kind {
        case .pencil, .highlighter:
            return SavedDrawingTool(
                id: value.id,
                kindRawValue: value.kind.rawValue,
                colorHex: canonicalColorHex(value.colorHex),
                width: canonicalInkWidth(value.width),
                opacity: canonicalOpacity(value.opacity),
                eraserModeRawValue: nil
            )
        case .eraser:
            return SavedDrawingTool(
                id: value.id,
                kindRawValue: GraphicTool.eraser.rawValue,
                colorHex: "#000000",
                width: canonicalEraserWidth(value.width),
                opacity: 1.0,
                eraserModeRawValue: value.eraserMode.rawValue
            )
        case .lasso:
            return SavedDrawingTool(
                id: value.id,
                kindRawValue: GraphicTool.pencil.rawValue,
                colorHex: "#000000",
                width: 1.5,
                opacity: 1.0,
                eraserModeRawValue: nil
            )
        }
    }

    private static func canonicalColorHex(_ raw: String) -> String {
        var value = raw.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
        if value.hasPrefix("#") { value.removeFirst() }
        if value.count == 8 { value = String(value.prefix(6)) }
        guard value.count == 6, value.allSatisfy(\.isHexDigit) else { return "#000000" }
        return "#\(value)"
    }

    private static func canonicalInkWidth(_ raw: Double) -> Double {
        let finite = raw.isFinite ? raw : 1.0
        let bounded = min(max(finite, 0.5), 60.0)
        return (bounded * 2.0).rounded() / 2.0
    }

    private static func canonicalEraserWidth(_ raw: Double) -> Double {
        let finite = raw.isFinite ? raw : 18.0
        let bounded = min(max(finite, 2.0), 120.0)
        return bounded.rounded()
    }

    private static func canonicalOpacity(_ raw: Double) -> Double {
        let finite = raw.isFinite ? raw : 1.0
        return (min(max(finite, 0.05), 1.0) * 20.0).rounded() / 20.0
    }

    private static let defaultErasers: [SavedDrawingTool] = [
        SavedDrawingTool(
            id: UUID(),
            kindRawValue: GraphicTool.eraser.rawValue,
            colorHex: "#000000",
            width: 18.0,
            opacity: 1.0,
            eraserModeRawValue: EraserMode.partial.rawValue
        ),
        SavedDrawingTool(
            id: UUID(),
            kindRawValue: GraphicTool.eraser.rawValue,
            colorHex: "#000000",
            width: 24.0,
            opacity: 1.0,
            eraserModeRawValue: EraserMode.whole.rawValue
        ),
    ]

    private static let defaultTools: [SavedDrawingTool] = [
        SavedDrawingTool(id: UUID(), kindRawValue: GraphicTool.pencil.rawValue, colorHex: "#000000", width: 1.5, opacity: 1.0, eraserModeRawValue: nil),
        SavedDrawingTool(id: UUID(), kindRawValue: GraphicTool.pencil.rawValue, colorHex: "#1971C2", width: 3.0, opacity: 1.0, eraserModeRawValue: nil),
        SavedDrawingTool(id: UUID(), kindRawValue: GraphicTool.pencil.rawValue, colorHex: "#C92A2A", width: 5.0, opacity: 1.0, eraserModeRawValue: nil),
        SavedDrawingTool(id: UUID(), kindRawValue: GraphicTool.highlighter.rawValue, colorHex: "#FFE066", width: 14.0, opacity: 0.35, eraserModeRawValue: nil),
        SavedDrawingTool(id: UUID(), kindRawValue: GraphicTool.highlighter.rawValue, colorHex: "#8CE99A", width: 18.0, opacity: 0.45, eraserModeRawValue: nil),
    ] + defaultErasers
}
