// Persist independently named node and connector styles between iPad sessions.

import Foundation
import SwiftUI

struct TikZSavedStylePreset: Codable, Identifiable {
    let id: UUID
    var name: String
    var tool: TikZCanvasTool
    var nodeStyle: TikZNodeStyle
    var edgeStyle: TikZEdgeStyle
}

@MainActor
final class TikZStylePresetStore: ObservableObject {
    @Published private(set) var presets: [TikZSavedStylePreset] = []

    private struct Snapshot: Codable {
        var presets: [TikZSavedStylePreset] = []
        var nodeStyles: [String: TikZNodeStyle] = [:]
        var edgeStyles: [String: TikZEdgeStyle] = [:]
    }

    private let storageKey = "nd.graphic.tikz.style.presets.v1"
    private var nodeStyles: [String: TikZNodeStyle] = [:]
    private var edgeStyles: [String: TikZEdgeStyle] = [:]

    init() {
        guard let data = UserDefaults.standard.data(forKey: storageKey),
              let snapshot = try? JSONDecoder().decode(Snapshot.self, from: data) else {
            return
        }
        presets = snapshot.presets
        nodeStyles = snapshot.nodeStyles
        edgeStyles = snapshot.edgeStyles
    }

    func nodeStyle(for shape: TikZNodeShape) -> TikZNodeStyle {
        nodeStyles[nodeStyleKey(for: shape)] ?? TikZNodeStyle()
    }

    func edgeStyle(for tool: TikZCanvasTool) -> TikZEdgeStyle {
        edgeStyles[tool.rawValue] ?? TikZEdgeStyle()
    }

    func remember(_ style: TikZNodeStyle, for shape: TikZNodeShape) {
        let key = nodeStyleKey(for: shape)
        guard nodeStyles[key] != style else { return }
        nodeStyles[key] = style
        persist()
    }

    private func nodeStyleKey(for shape: TikZNodeShape) -> String {
        // One round-shape tool owns both the circle and ellipse style.
        shape == .circle ? TikZNodeShape.ellipse.rawValue : shape.rawValue
    }

    func remember(_ style: TikZEdgeStyle, for tool: TikZCanvasTool) {
        guard tool.connectorKind != nil,
              edgeStyles[tool.rawValue] != style else { return }
        edgeStyles[tool.rawValue] = style
        persist()
    }

    func save(
        name: String,
        tool: TikZCanvasTool,
        nodeStyle: TikZNodeStyle,
        edgeStyle: TikZEdgeStyle
    ) {
        let trimmed = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, tool != .select else { return }
        presets.append(TikZSavedStylePreset(
            id: UUID(),
            name: trimmed,
            tool: tool,
            nodeStyle: nodeStyle,
            edgeStyle: edgeStyle
        ))
        persist()
    }

    func delete(_ id: UUID) {
        presets.removeAll { $0.id == id }
        persist()
    }

    private func persist() {
        let snapshot = Snapshot(
            presets: presets,
            nodeStyles: nodeStyles,
            edgeStyles: edgeStyles
        )
        guard let data = try? JSONEncoder().encode(snapshot) else { return }
        UserDefaults.standard.set(data, forKey: storageKey)
    }
}
