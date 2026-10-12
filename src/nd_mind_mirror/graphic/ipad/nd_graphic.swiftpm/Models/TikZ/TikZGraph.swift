// Canonical lightweight graph model parsed from editable TikZ source.

import CoreGraphics
import Foundation

enum TikZNodeShape: String, CaseIterable, Identifiable, Codable {
    case rectangle
    case ellipse
    case circle
    case triangle
    var id: String { rawValue }
}

struct TikZNode: Identifiable, Hashable {
    let name: String
    var label: String
    var position: CGPoint
    var width: Double
    var height: Double
    var shape: TikZNodeShape
    var fillColor: TikZColorValue
    var strokeColor: TikZColorValue
    var textColor: TikZColorValue
    var lineWidth: Double

    var id: String { name }
    var style: TikZNodeStyle {
        TikZNodeStyle(
            fillColor: fillColor,
            strokeColor: strokeColor,
            textColor: textColor,
            lineWidth: lineWidth
        )
    }
}

struct TikZEdge: Identifiable, Hashable {
    let id: String
    let source: String
    let target: String
    var label: String
    var directed: Bool
    var strokeColor: TikZColorValue
    var textColor: TikZColorValue
    var lineWidth: Double
    var linePattern: TikZLinePattern
    var arrowHeadStyle: TikZArrowHeadStyle
    var geometry: TikZConnectorGeometry

    var style: TikZEdgeStyle {
        TikZEdgeStyle(
            strokeColor: strokeColor,
            textColor: textColor,
            lineWidth: lineWidth,
            directed: directed,
            linePattern: linePattern,
            arrowHeadStyle: arrowHeadStyle
        )
    }
}

struct TikZGraph {
    var nodes: [TikZNode]
    var edges: [TikZEdge]
    static let empty = TikZGraph(nodes: [], edges: [])
}
