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
            let options = match.range(at: 1).location == NSNotFound ? "" : nsSource.substring(with: match.range(at: 1))
            let name = nsSource.substring(with: match.range(at: 2))
            let label = nsSource.substring(with: match.range(at: 5))
            let shape: TikZNodeShape = options.range(of: "ellipse", options: .caseInsensitive) != nil || options.range(of: "circle", options: .caseInsensitive) != nil ? .ellipse : .rectangle
            return TikZNode(
                name: name,
                label: label,
                position: CGPoint(x: x, y: y),
                width: optionDimension("minimum width", options: options) ?? (shape == .ellipse ? 1.8 : 2.0),
                height: optionDimension("minimum height", options: options) ?? (shape == .ellipse ? 1.1 : 1.0),
                shape: shape
            )
        }
    }

    static func parseEdges(_ source: String) -> [TikZEdge] {
        let pattern = #"\\draw\s*(?:\[([^\]]*)\])?\s*\(([^\)]+)\)\s*--\s*(?:node(?:\[[^\]]*\])?\s*\{([^{}]*)\}\s*)?\(([^\)]+)\)\s*;"#
        guard let regex = try? NSRegularExpression(pattern: pattern) else { return [] }
        let nsSource = source as NSString
        let range = NSRange(location: 0, length: nsSource.length)
        var counts: [String: Int] = [:]
        return regex.matches(in: source, range: range).compactMap { match in
            guard match.numberOfRanges == 5 else { return nil }
            let options = match.range(at: 1).location == NSNotFound ? "" : nsSource.substring(with: match.range(at: 1))
            let sourceName = nsSource.substring(with: match.range(at: 2))
            let label = match.range(at: 3).location == NSNotFound ? "" : nsSource.substring(with: match.range(at: 3))
            let targetName = nsSource.substring(with: match.range(at: 4))
            let base = "\(sourceName)->\(targetName)"
            let occurrence = counts[base, default: 0]
            counts[base] = occurrence + 1
            return TikZEdge(
                id: "\(base)#\(occurrence)",
                source: sourceName,
                target: targetName,
                label: label,
                directed: options.contains("->") || options.contains("latex")
            )
        }
    }

    private static func optionDimension(_ key: String, options: String) -> Double? {
        let escaped = NSRegularExpression.escapedPattern(for: key)
        let pattern = escaped + #"\s*=\s*([0-9.]+)\s*(?:cm)?"#
        guard let regex = try? NSRegularExpression(pattern: pattern, options: [.caseInsensitive]) else { return nil }
        let nsOptions = options as NSString
        let range = NSRange(location: 0, length: nsOptions.length)
        guard let match = regex.firstMatch(in: options, range: range), match.numberOfRanges > 1 else { return nil }
        return Double(nsOptions.substring(with: match.range(at: 1)))
    }
}
