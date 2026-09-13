// Source-preserving TikZ edits for named nodes and simple named-node edges.

import CoreGraphics
import Foundation

enum TikZSourceEditor {
    private static let mapper = TikZCoordinateMapper()

    static func addNode(shape: TikZNodeShape, at point: CGPoint, to source: String) -> String {
        let name = nextNodeName(in: source)
        let dimensions = shape == .ellipse ? (1.8, 1.1) : (2.0, 1.0)
        let command = "\\node[draw, \(shape.rawValue), minimum width=\(mapper.number(dimensions.0))cm, minimum height=\(mapper.number(dimensions.1))cm] (\(name)) at (\(mapper.number(Double(point.x))),\(mapper.number(Double(point.y)))) {};"
        return appending(command: command, to: source)
    }

    static func moveNode(named name: String, to point: CGPoint, in source: String) -> String {
        replacingNode(named: name, in: source) { options, name, _, _, label in
            "\\node\(options.isEmpty ? "" : "[\(options)]") (\(name)) at (\(mapper.number(Double(point.x))),\(mapper.number(Double(point.y)))) {\(label)};"
        }
    }

    static func updateNodeLabel(named name: String, label: String, in source: String) -> String {
        replacingNode(named: name, in: source) { options, name, x, y, _ in
            "\\node\(options.isEmpty ? "" : "[\(options)]") (\(name)) at (\(x),\(y)) {\(escape(label))};"
        }
    }

    static func addEdge(from sourceNode: String, to targetNode: String, label: String, in source: String) -> String {
        let labelPart = label.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? "" : " node[midway, fill=white, inner sep=1pt] {\(escape(label))}"
        return appending(command: "\\draw[->] (\(sourceNode)) --\(labelPart) (\(targetNode));", to: source)
    }

    static func updateEdgeLabel(edgeID: String, label: String, in source: String) -> String {
        let edges = TikZGraphParser.parseEdges(source)
        guard let target = edges.first(where: { $0.id == edgeID }) else { return source }
        let pattern = #"\\draw\s*(?:\[([^\]]*)\])?\s*\("# + NSRegularExpression.escapedPattern(for: target.source) + #"\)\s*--\s*(?:node(?:\[[^\]]*\])?\s*\{([^{}]*)\}\s*)?\("# + NSRegularExpression.escapedPattern(for: target.target) + #"\)\s*;"#
        guard let regex = try? NSRegularExpression(pattern: pattern) else { return source }
        let nsSource = source as NSString
        let searchRange = NSRange(location: 0, length: nsSource.length)
        let occurrence = Int(edgeID.split(separator: "#").last ?? "0") ?? 0
        let matches = regex.matches(in: source, range: searchRange)
        guard occurrence < matches.count else { return source }
        let match = matches[occurrence]
        let options = match.range(at: 1).location == NSNotFound ? "->" : nsSource.substring(with: match.range(at: 1))
        let labelPart = label.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? "" : " node[midway, fill=white, inner sep=1pt] {\(escape(label))}"
        let replacement = "\\draw[\(options)] (\(target.source)) --\(labelPart) (\(target.target));"
        let mutable = NSMutableString(string: source)
        mutable.replaceCharacters(in: match.range(at: 0), with: replacement)
        return mutable as String
    }

    static func applyPositions(_ positions: [String: CGPoint], to source: String) -> String {
        positions.keys.sorted().reduce(source) { partial, name in
            guard let point = positions[name] else { return partial }
            return moveNode(named: name, to: point, in: partial)
        }
    }

    static func appending(command: String, to source: String) -> String {
        let end = "\\end{tikzpicture}"
        if let range = source.range(of: end, options: .backwards) {
            var result = source
            let prefix = source[..<range.lowerBound].hasSuffix("\n") ? "" : "\n"
            result.insert(contentsOf: prefix + "    \(command)\n", at: range.lowerBound)
            return result
        }
        if source.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return "\\begin{tikzpicture}\n    \(command)\n\\end{tikzpicture}\n"
        }
        return source + (source.hasSuffix("\n") ? "" : "\n") + command + "\n"
    }

    private static func replacingNode(
        named wantedName: String,
        in source: String,
        transform: (_ options: String, _ name: String, _ x: String, _ y: String, _ label: String) -> String
    ) -> String {
        let pattern = #"\\node\s*(?:\[([^\]]*)\]\s*)?\(([^\)]+)\)\s*at\s*\((-?[0-9.]+)\s*,\s*(-?[0-9.]+)\)\s*\{([^{}]*)\}\s*;"#
        guard let regex = try? NSRegularExpression(pattern: pattern) else { return source }
        let nsSource = source as NSString
        let range = NSRange(location: 0, length: nsSource.length)
        for match in regex.matches(in: source, range: range) where match.numberOfRanges == 6 {
            let name = nsSource.substring(with: match.range(at: 2))
            guard name == wantedName else { continue }
            let options = match.range(at: 1).location == NSNotFound ? "" : nsSource.substring(with: match.range(at: 1))
            let replacement = transform(
                options,
                name,
                nsSource.substring(with: match.range(at: 3)),
                nsSource.substring(with: match.range(at: 4)),
                nsSource.substring(with: match.range(at: 5))
            )
            let mutable = NSMutableString(string: source)
            mutable.replaceCharacters(in: match.range(at: 0), with: replacement)
            return mutable as String
        }
        return source
    }

    private static func nextNodeName(in source: String) -> String {
        let pattern = #"\(ndNode([0-9]+)\)"#
        guard let regex = try? NSRegularExpression(pattern: pattern) else { return "ndNode1" }
        let nsSource = source as NSString
        let range = NSRange(location: 0, length: nsSource.length)
        let maximum = regex.matches(in: source, range: range).compactMap { match -> Int? in
            guard match.numberOfRanges > 1 else { return nil }
            return Int(nsSource.substring(with: match.range(at: 1)))
        }.max() ?? 0
        return "ndNode\(maximum + 1)"
    }

    private static func escape(_ text: String) -> String {
        text.map { character -> String in
            switch character {
            case "\\": return "\\textbackslash{}"
            case "&": return "\\&"
            case "%": return "\\%"
            case "$": return "\\$"
            case "#": return "\\#"
            case "_": return "\\_"
            case "{": return "\\{"
            case "}": return "\\}"
            default: return String(character)
            }
        }.joined()
    }
}
