// Parse the conservative named-node and named-edge TikZ subset used by the visual editor.

import CoreGraphics
import Foundation

enum TikZGraphParser {
    static func parse(_ source: String) -> TikZGraph {
        TikZGraph(nodes: parseNodes(source), edges: parseEdges(source))
    }

    static func parseNodes(_ source: String) -> [TikZNode] {
        let pattern = #"\\node\s*(?:\[([^\]]*)\]\s*)?\(([^\)]+)\)\s*at\s*\((-?[0-9.]+)\s*,\s*(-?[0-9.]+)\)\s*\{([^{}]*)\}\s*;"#
        guard let regex = try? NSRegularExpression(pattern: pattern) else { return [] }
        let nsSource = source as NSString
        let range = NSRange(location: 0, length: nsSource.length)
        return regex.matches(in: source, range: range).compactMap { match in
            guard match.numberOfRanges == 6,
                  let x = Double(nsSource.substring(with: match.range(at: 3))),
                  let y = Double(nsSource.substring(with: match.range(at: 4))) else { return nil }
            let rawOptions = match.range(at: 1).location == NSNotFound ? "" : nsSource.substring(with: match.range(at: 1))
            let options = TikZOptionList(rawOptions)
            let name = nsSource.substring(with: match.range(at: 2))
            let label = nsSource.substring(with: match.range(at: 5))
            let shape: TikZNodeShape = options.containsFlag("ellipse") || options.containsFlag("circle") ? .ellipse : .rectangle
            return TikZNode(
                name: name,
                label: label,
                position: CGPoint(x: x, y: y),
                width: optionMeasurement("minimum width", options: options) ?? (shape == .ellipse ? 1.8 : 2.0),
                height: optionMeasurement("minimum height", options: options) ?? (shape == .ellipse ? 1.1 : 1.0),
                shape: shape,
                fillColor: TikZColorValue.fromTikZ(options.value(for: "fill")) ?? .white,
                strokeColor: TikZColorValue.fromTikZ(options.value(for: "draw")) ?? .black,
                textColor: TikZColorValue.fromTikZ(options.value(for: "text")) ?? .black,
                lineWidth: optionMeasurement("line width", options: options) ?? 1.0
            )
        }
    }

    static func parseEdges(_ source: String) -> [TikZEdge] {
        let pattern = #"\\draw\s*(?:\[((?:[^\[\]]|\[[^\]]*\])*)\])?\s*\(([^\)]+)\)\s*--\s*(?:node(?:\[([^\]]*)\])?\s*\{([^{}]*)\}\s*)?\(([^\)]+)\)\s*;"#
        guard let regex = try? NSRegularExpression(pattern: pattern) else { return [] }
        let nsSource = source as NSString
        let range = NSRange(location: 0, length: nsSource.length)
        var counts: [String: Int] = [:]
        return regex.matches(in: source, range: range).compactMap { match in
            guard match.numberOfRanges == 6 else { return nil }
            let rawOptions = match.range(at: 1).location == NSNotFound ? "" : nsSource.substring(with: match.range(at: 1))
            let labelOptionsRaw = match.range(at: 3).location == NSNotFound ? "" : nsSource.substring(with: match.range(at: 3))
            let options = TikZOptionList(rawOptions)
            let labelOptions = TikZOptionList(labelOptionsRaw)
            let sourceName = nsSource.substring(with: match.range(at: 2))
            let label = match.range(at: 4).location == NSNotFound ? "" : nsSource.substring(with: match.range(at: 4))
            let targetName = nsSource.substring(with: match.range(at: 5))
            let base = "\(sourceName)->\(targetName)"
            let occurrence = counts[base, default: 0]
            counts[base] = occurrence + 1
            let directed = options.containsFlag("->")
                || rawOptions.contains("-{Latex}")
                || rawOptions.localizedCaseInsensitiveContains("latex")
            let arrowHeadStyle: TikZArrowHeadStyle = rawOptions.contains("Latex[open]")
                ? .open
                : .filled
            return TikZEdge(
                id: "\(base)#\(occurrence)",
                source: sourceName,
                target: targetName,
                label: label,
                directed: directed,
                strokeColor: TikZColorValue.fromTikZ(options.value(for: "draw")) ?? .black,
                textColor: TikZColorValue.fromTikZ(labelOptions.value(for: "text")) ?? .black,
                lineWidth: optionMeasurement("line width", options: options) ?? 1.0,
                linePattern: options.containsFlag("dashed") ? .dashed : .solid,
                arrowHeadStyle: arrowHeadStyle
            )
        }
    }

    private static func optionMeasurement(_ key: String, options: TikZOptionList) -> Double? {
        guard let raw = options.value(for: key) else { return nil }
        let numeric = raw
            .replacingOccurrences(of: "cm", with: "", options: .caseInsensitive)
            .replacingOccurrences(of: "pt", with: "", options: .caseInsensitive)
            .trimmingCharacters(in: .whitespacesAndNewlines)
        return Double(numeric)
    }
}
