import CoreGraphics
import Foundation

struct TikZEditResult {
    let source: String
    let summary: String
}

enum TikZSourceEditor {
    static func command(
        for tool: DrawingTool,
        rawPoints: [CGPoint],
        canvasSize: CGSize,
        source: String,
        mapper: TikZCoordinateMapper = TikZCoordinateMapper()
    ) -> String? {
        guard rawPoints.count >= 2 else { return nil }
        let first = mapper.map(rawPoints.first!, in: canvasSize)
        let last = mapper.map(rawPoints.last!, in: canvasSize)

        switch tool {
        case .line:
            return "\\draw \(mapper.format(first)) -- \(mapper.format(last));"
        case .arrow:
            return "\\draw[->] \(mapper.format(first)) -- \(mapper.format(last));"
        case .rectangle:
            let box = boundingBox(rawPoints)
            return nodeCommand(
                shape: "rectangle",
                box: box,
                canvasSize: canvasSize,
                source: source,
                mapper: mapper
            )
        case .ellipse:
            let box = boundingBox(rawPoints)
            return nodeCommand(
                shape: "ellipse",
                box: box,
                canvasSize: canvasSize,
                source: source,
                mapper: mapper
            )
        case .freehand:
            let simplified = PolylineSimplifier.simplify(rawPoints, epsilon: 2.5)
            let coordinates = simplified
                .map { mapper.format(mapper.map($0, in: canvasSize)) }
                .joined(separator: " ")
            return "\\draw[smooth] plot coordinates { \(coordinates) };"
        case .text:
            return nil
        }
    }

    static func applyingRecognizedText(
        _ recognition: HandwritingRecognition,
        canvasSize: CGSize,
        to source: String,
        mapper: TikZCoordinateMapper = TikZCoordinateMapper()
    ) -> TikZEditResult {
        let escaped = escapeLatexText(recognition.text)
        let point = mapper.map(recognition.center, in: canvasSize)

        if let match = bestContainingNode(
            for: point,
            in: source,
            mapper: mapper
        ) {
            let existing = match.content.trimmingCharacters(in: .whitespacesAndNewlines)
            let replacementText = existing.isEmpty ? escaped : existing + " " + escaped
            let updated = replacingNodeContent(match, with: replacementText, in: source)
            return TikZEditResult(
                source: updated,
                summary: "Recognized “\(recognition.text)” inside node \(match.name)"
            )
        }

        let command = "\\node at \(mapper.format(point)) {\(escaped)};"
        return TikZEditResult(
            source: appending(command: command, to: source),
            summary: "Recognized “\(recognition.text)” as a TikZ text label"
        )
    }

    static func appending(command: String, to source: String) -> String {
        let end = "\\end{tikzpicture}"
        if let range = source.range(of: end, options: .backwards) {
            var result = source
            let insertion = (source[..<range.lowerBound].hasSuffix("\n") ? "" : "\n") + "    \(command)\n"
            result.insert(contentsOf: insertion, at: range.lowerBound)
            return result
        }

        if source.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return "\\begin{tikzpicture}\n    \(command)\n\\end{tikzpicture}\n"
        }

        return source + (source.hasSuffix("\n") ? "" : "\n") + command + "\n"
    }

    private static func nodeCommand(
        shape: String,
        box: CGRect,
        canvasSize: CGSize,
        source: String,
        mapper: TikZCoordinateMapper
    ) -> String {
        let center = mapper.map(CGPoint(x: box.midX, y: box.midY), in: canvasSize)
        let width = max(0.35, Double(box.width / max(canvasSize.width, 1)) * mapper.canvasWidth)
        let height = max(0.35, Double(box.height / max(canvasSize.height, 1)) * mapper.canvasHeight)
        let name = nextNodeName(in: source)
        return "\\node[draw, \(shape), inner sep=0pt, minimum width=\(mapper.number(width))cm, minimum height=\(mapper.number(height))cm] (\(name)) at \(mapper.format(center)) {};"
    }

    private static func nextNodeName(in source: String) -> String {
        let pattern = #"\(ndsketchNode([0-9]+)\)"#
        guard let regex = try? NSRegularExpression(pattern: pattern) else {
            return "ndsketchNode1"
        }
        let nsSource = source as NSString
        let range = NSRange(location: 0, length: nsSource.length)
        let maximum = regex.matches(in: source, range: range).compactMap { match -> Int? in
            guard match.numberOfRanges > 1 else { return nil }
            return Int(nsSource.substring(with: match.range(at: 1)))
        }.max() ?? 0
        return "ndsketchNode\(maximum + 1)"
    }

    private struct EditableNodeMatch {
        let fullRange: NSRange
        let contentRange: NSRange
        let name: String
        let content: String
        let center: CGPoint
        let width: Double
        let height: Double
    }

    private static func bestContainingNode(
        for point: CGPoint,
        in source: String,
        mapper: TikZCoordinateMapper
    ) -> EditableNodeMatch? {
        // Intentionally targets the common editable TikZ node form. Complex source
        // remains untouched; if a node cannot be parsed, handwriting becomes a
        // standalone label instead of risking source corruption.
        let pattern = #"\\node\s*(?:\[([^\]]*)\]\s*)?(?:\(([^\)]+)\)\s*)?at\s*\((-?[0-9.]+)\s*,\s*(-?[0-9.]+)\)\s*\{([^{}]*)\}\s*;"#
        guard let regex = try? NSRegularExpression(pattern: pattern) else { return nil }
        let nsSource = source as NSString
        let searchRange = NSRange(location: 0, length: nsSource.length)
        var candidates: [(EditableNodeMatch, Double)] = []

        for match in regex.matches(in: source, range: searchRange) {
            guard match.numberOfRanges == 6,
                  let x = Double(nsSource.substring(with: match.range(at: 3))),
                  let y = Double(nsSource.substring(with: match.range(at: 4))) else { continue }

            let optionRange = match.range(at: 1)
            let nameRange = match.range(at: 2)
            let options = optionRange.location == NSNotFound ? "" : nsSource.substring(with: optionRange)
            let name = nameRange.location == NSNotFound ? "unnamed" : nsSource.substring(with: nameRange)
            let content = nsSource.substring(with: match.range(at: 5))
            let width = optionDimension("minimum width", in: options) ?? defaultWidth(for: options)
            let height = optionDimension("minimum height", in: options) ?? defaultHeight(for: options)
            let center = CGPoint(x: x, y: y)
            let dx = Double(point.x - center.x)
            let dy = Double(point.y - center.y)

            let contains: Bool
            if options.range(of: "circle", options: .caseInsensitive) != nil ||
                options.range(of: "ellipse", options: .caseInsensitive) != nil {
                let rx = max(width / 2, 0.001)
                let ry = max(height / 2, 0.001)
                contains = (dx * dx) / (rx * rx) + (dy * dy) / (ry * ry) <= 1.35
            } else {
                contains = abs(dx) <= width * 0.58 && abs(dy) <= height * 0.58
            }
            guard contains else { continue }

            let distance = dx * dx + dy * dy
            candidates.append((EditableNodeMatch(
                fullRange: match.range(at: 0),
                contentRange: match.range(at: 5),
                name: name,
                content: content,
                center: center,
                width: width,
                height: height
            ), distance))
        }

        return candidates.min(by: { $0.1 < $1.1 })?.0
    }

    private static func replacingNodeContent(
        _ match: EditableNodeMatch,
        with newText: String,
        in source: String
    ) -> String {
        let mutable = NSMutableString(string: source)
        mutable.replaceCharacters(in: match.contentRange, with: newText)
        return mutable as String
    }

    private static func optionDimension(_ key: String, in options: String) -> Double? {
        let escapedKey = NSRegularExpression.escapedPattern(for: key)
        let pattern = escapedKey + #"\s*=\s*([0-9.]+)\s*(?:cm)?"#
        guard let regex = try? NSRegularExpression(pattern: pattern, options: [.caseInsensitive]) else { return nil }
        let nsOptions = options as NSString
        let range = NSRange(location: 0, length: nsOptions.length)
        guard let match = regex.firstMatch(in: options, range: range), match.numberOfRanges > 1 else { return nil }
        return Double(nsOptions.substring(with: match.range(at: 1)))
    }

    private static func defaultWidth(for options: String) -> Double {
        if options.range(of: "circle", options: .caseInsensitive) != nil { return 1.2 }
        if options.range(of: "ellipse", options: .caseInsensitive) != nil { return 1.8 }
        return 2.0
    }

    private static func defaultHeight(for options: String) -> Double {
        if options.range(of: "circle", options: .caseInsensitive) != nil { return 1.2 }
        if options.range(of: "ellipse", options: .caseInsensitive) != nil { return 1.1 }
        return 1.0
    }

    private static func escapeLatexText(_ text: String) -> String {
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
            case "~": return "\\textasciitilde{}"
            case "^": return "\\textasciicircum{}"
            default: return String(character)
            }
        }.joined()
    }

    private static func boundingBox(_ points: [CGPoint]) -> CGRect {
        let xs = points.map(\.x)
        let ys = points.map(\.y)
        return CGRect(
            x: xs.min() ?? 0,
            y: ys.min() ?? 0,
            width: (xs.max() ?? 0) - (xs.min() ?? 0),
            height: (ys.max() ?? 0) - (ys.min() ?? 0)
        )
    }
}
