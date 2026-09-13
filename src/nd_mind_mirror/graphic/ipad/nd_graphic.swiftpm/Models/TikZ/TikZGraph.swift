// Canonical lightweight graph model parsed from editable TikZ source.

import CoreGraphics
import Foundation

enum TikZNodeShape: String, CaseIterable, Identifiable {
    case rectangle
    case ellipse

    var id: String { rawValue }
}

struct TikZNode: Identifiable, Hashable {
    let name: String
    var label: String
    var position: CGPoint
    var width: Double
    var height: Double
    var shape: TikZNodeShape

    var id: String { name }
}

struct TikZEdge: Identifiable, Hashable {
    let id: String
    let source: String
    let target: String
    var label: String
    var directed: Bool
}

struct TikZGraph {
    var nodes: [TikZNode]
    var edges: [TikZEdge]

    static let empty = TikZGraph(nodes: [], edges: [])
}
