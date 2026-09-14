// Source-preserving TikZ edits for named nodes, simple edges, ordering, and canvas metadata.

import CoreGraphics
import Foundation

enum TikZSourceEditor {
    private static let mapper = TikZCoordinateMapper()

    static func addNode(
        shape: TikZNodeShape,
        center: CGPoint,
        size: CGSize,
        style: TikZNodeStyle,
        label: String,
        to source: String
    ) -> String {
        let name = nextNodeName(in: source)
        var prepared = source
        if shape == .ellipse {
            prepared = TikZSourceDependencyManager
                .ensuringShapesGeometric(
                    in: prepared
                )
        }

        var options = TikZOptionList("")
        applyNodeStyle(style, to: &options)
        options.setFlag(shape.rawValue, enabled: true)
        options.setValue(
            "\(mapper.number(max(Double(size.width), 0.2)))cm",
            for: "minimum width"
        )
        options.setValue(
            "\(mapper.number(max(Double(size.height), 0.2)))cm",
            for: "minimum height"
        )
        let command =
            "\\node[\(options.serialized)] (\(name)) at "
            + "(\(mapper.number(Double(center.x))),\(mapper.number(Double(center.y)))) "
            + "{\(escape(label))};"
        return appending(command: command, to: prepared)
    }

    static func moveNode(
        named name: String,
        to point: CGPoint,
        in source: String
    ) -> String {
        replacingNode(named: name, in: source) {
            options,
            nodeName,
            _,
            _,
            label
            in
            "\\node\(options.isEmpty ? "" : "[\(options)]") "
                + "(\(nodeName)) at "
                + "(\(mapper.number(Double(point.x))),\(mapper.number(Double(point.y)))) "
                + "{\(label)};"
        }
    }

    static func resizeNode(
        named name: String,
        center: CGPoint,
        size: CGSize,
        in source: String
    ) -> String {
        replacingNode(named: name, in: source) {
            rawOptions,
            nodeName,
            _,
            _,
            label
            in
            var options = TikZOptionList(rawOptions)
            options.setValue(
                "\(mapper.number(max(Double(size.width), 0.2)))cm",
                for: "minimum width"
            )
            options.setValue(
                "\(mapper.number(max(Double(size.height), 0.2)))cm",
                for: "minimum height"
            )
            return "\\node[\(options.serialized)] "
                + "(\(nodeName)) at "
                + "(\(mapper.number(Double(center.x))),\(mapper.number(Double(center.y)))) "
                + "{\(label)};"
        }
    }

    static func updateNodeLabel(
        named name: String,
        label: String,
        in source: String
    ) -> String {
        replacingNode(named: name, in: source) {
            options,
            nodeName,
            x,
            y,
            _
            in
            "\\node\(options.isEmpty ? "" : "[\(options)]") "
                + "(\(nodeName)) at (\(x),\(y)) "
                + "{\(escape(label))};"
        }
    }

    static func updateNodeStyle(
        named name: String,
        style: TikZNodeStyle,
        in source: String
    ) -> String {
        replacingNode(named: name, in: source) {
            rawOptions,
            nodeName,
            x,
            y,
            label
            in
            var options = TikZOptionList(rawOptions)
            applyNodeStyle(style, to: &options)
            return "\\node[\(options.serialized)] "
                + "(\(nodeName)) at (\(x),\(y)) "
                + "{\(label)};"
        }
    }

    static func duplicateNode(
        named name: String,
        in source: String
    ) -> String {
        guard
            let node = TikZGraphParser
                .parseNodes(source)
                .first(where: { $0.name == name })
        else {
            return source
        }

        return addNode(
            shape: node.shape,
            center: CGPoint(
                x: node.position.x + 0.45,
                y: node.position.y + 0.45
            ),
            size: CGSize(
                width: node.width,
                height: node.height
            ),
            style: node.style,
            label: node.label,
            to: source
        )
    }

    static func deleteNode(
        named name: String,
        in source: String
    ) -> String {
        let connected = TikZGraphParser
            .parseEdges(source)
            .filter {
                $0.source == name
                    || $0.target == name
            }

        var result = connected
            .reversed()
            .reduce(source) {
                partial,
                edge
                in
                deleteEdge(
                    edgeID: edge.id,
                    in: partial
                )
            }

        result = replacingNode(
            named: name,
            in: result
        ) { _, _, _, _, _ in
            ""
        }

        return normalizeBlankLines(result)
    }

    static func bringNodeToFront(
        named name: String,
        in source: String
    ) -> String {
        moveNodeCommand(
            named: name,
            in: source,
            toFront: true
        )
    }

    static func sendNodeToBack(
        named name: String,
        in source: String
    ) -> String {
        moveNodeCommand(
            named: name,
            in: source,
            toFront: false
        )
    }

    static func addEdge(
        from sourceNode: String,
        to targetNode: String,
        label: String,
        style: TikZEdgeStyle,
        in source: String
    ) -> String {
        var prepared = source
        if style.directed {
            prepared = TikZSourceDependencyManager
                .ensuringArrowsMeta(
                    in: prepared
                )
        }

        var options = TikZOptionList("")
        applyEdgeStyle(style, to: &options)
        return appending(
            command: "\\draw[\(options.serialized)] "
                + "(\(sourceNode)) --"
                + "\(edgeLabelPart(label, textColor: style.textColor)) "
                + "(\(targetNode));",
            to: prepared
        )
    }

    static func updateEdgeLabel(
        edgeID: String,
        label: String,
        style: TikZEdgeStyle,
        in source: String
    ) -> String {
        replacingEdge(
            edgeID: edgeID,
            in: source
        ) {
            options,
            sourceNode,
            targetNode,
            _
            in
            "\\draw\(options.isEmpty ? "" : "[\(options)]") "
                + "(\(sourceNode)) --"
                + "\(edgeLabelPart(label, textColor: style.textColor)) "
                + "(\(targetNode));"
        }
    }

    static func updateEdgeStyle(
        edgeID: String,
        style: TikZEdgeStyle,
        in source: String
    ) -> String {
        var prepared = source
        if style.directed {
            prepared = TikZSourceDependencyManager
                .ensuringArrowsMeta(
                    in: prepared
                )
        }

        return replacingEdge(
            edgeID: edgeID,
            in: prepared
        ) {
            rawOptions,
            sourceNode,
            targetNode,
            label
            in
            var options = TikZOptionList(rawOptions)
            applyEdgeStyle(style, to: &options)
            return "\\draw[\(options.serialized)] "
                + "(\(sourceNode)) --"
                + "\(edgeLabelPart(label, textColor: style.textColor)) "
                + "(\(targetNode));"
        }
    }

    static func deleteEdge(
        edgeID: String,
        in source: String
    ) -> String {
        normalizeBlankLines(
            replacingEdge(
                edgeID: edgeID,
                in: source
            ) { _, _, _, _ in
                ""
            }
        )
    }

    static func bringEdgeToFront(
        edgeID: String,
        in source: String
    ) -> String {
        moveEdgeCommand(
            edgeID: edgeID,
            in: source,
            toFront: true
        )
    }

    static func sendEdgeToBack(
        edgeID: String,
        in source: String
    ) -> String {
        moveEdgeCommand(
            edgeID: edgeID,
            in: source,
            toFront: false
        )
    }

    static func updateCanvasSize(
        _ size: CGSize,
        in source: String
    ) -> String {
        TikZCanvasMetadata.updating(
            source: source,
            size: size
        )
    }

    static func applyPositions(
        _ positions: [String: CGPoint],
        to source: String
    ) -> String {
        positions
            .keys
            .sorted()
            .reduce(source) {
                partial,
                name
                in
                guard
                    let point = positions[name]
                else {
                    return partial
                }
                return moveNode(
                    named: name,
                    to: point,
                    in: partial
                )
            }
    }

    static func appending(
        command: String,
        to source: String
    ) -> String {
        let end = "\\end{tikzpicture}"
        if let range = source.range(
            of: end,
            options: .backwards
        ) {
            var result = source
            let prefix = source[..<range.lowerBound]
                .hasSuffix("\n")
                ? ""
                : "\n"
            result.insert(
                contentsOf: prefix
                    + "    \(command)\n",
                at: range.lowerBound
            )
            return result
        }

        if source
            .trimmingCharacters(
                in: .whitespacesAndNewlines
            )
            .isEmpty
        {
            return "\\begin{tikzpicture}\n"
                + "    \(command)\n"
                + "\\end{tikzpicture}\n"
        }

        return source
            + (source.hasSuffix("\n") ? "" : "\n")
            + command
            + "\n"
    }

    private static func applyNodeStyle(
        _ style: TikZNodeStyle,
        to options: inout TikZOptionList
    ) {
        options.setValue(
            style.strokeColor.tikzValue,
            for: "draw"
        )
        options.setValue(
            style.fillColor.tikzValue,
            for: "fill"
        )
        options.setValue(
            style.textColor.tikzValue,
            for: "text"
        )
        options.setValue(
            "\(mapper.number(style.lineWidth))pt",
            for: "line width"
        )
    }

    private static func applyEdgeStyle(
        _ style: TikZEdgeStyle,
        to options: inout TikZOptionList
    ) {
        options.setValue(
            style.strokeColor.tikzValue,
            for: "draw"
        )
        options.setValue(
            "\(mapper.number(style.lineWidth))pt",
            for: "line width"
        )
        options.setFlag(
            "dashed",
            enabled: style.linePattern == .dashed
        )
        options.setFlag(
            "->",
            enabled: false
        )
        options.setFlag(
            "-{Latex}",
            enabled: false
        )
        options.setFlag(
            "-{Latex[open]}",
            enabled: false
        )

        if style.directed {
            switch style.arrowHeadStyle {
            case .filled:
                options.setFlag(
                    "-{Latex}",
                    enabled: true
                )
            case .open:
                options.setFlag(
                    "-{Latex[open]}",
                    enabled: true
                )
            }
        }
    }

    private static func replacingNode(
        named wantedName: String,
        in source: String,
        transform: (
            _ options: String,
            _ name: String,
            _ x: String,
            _ y: String,
            _ label: String
        ) -> String
    ) -> String {
        guard
            let match = nodeMatch(
                named: wantedName,
                in: source
            )
        else {
            return source
        }

        let nsSource = source as NSString
        let options = match.range(at: 1).location == NSNotFound
            ? ""
            : nsSource.substring(
                with: match.range(at: 1)
            )
        let replacement = transform(
            options,
            nsSource.substring(
                with: match.range(at: 2)
            ),
            nsSource.substring(
                with: match.range(at: 3)
            ),
            nsSource.substring(
                with: match.range(at: 4)
            ),
            nsSource.substring(
                with: match.range(at: 5)
            )
        )

        let mutable = NSMutableString(
            string: source
        )
        mutable.replaceCharacters(
            in: match.range(at: 0),
            with: replacement
        )
        return mutable as String
    }

    private static func replacingEdge(
        edgeID: String,
        in source: String,
        transform: (
            _ options: String,
            _ sourceNode: String,
            _ targetNode: String,
            _ label: String
        ) -> String
    ) -> String {
        guard
            let match = edgeMatch(
                edgeID: edgeID,
                in: source
            ),
            let target = TikZGraphParser
                .parseEdges(source)
                .first(
                    where: {
                        $0.id == edgeID
                    }
                )
        else {
            return source
        }

        let nsSource = source as NSString
        let options = match.range(at: 1).location == NSNotFound
            ? ""
            : nsSource.substring(
                with: match.range(at: 1)
            )
        let label = match.range(at: 2).location == NSNotFound
            ? ""
            : nsSource.substring(
                with: match.range(at: 2)
            )
        let replacement = transform(
            options,
            target.source,
            target.target,
            label
        )

        let mutable = NSMutableString(
            string: source
        )
        mutable.replaceCharacters(
            in: match.range(at: 0),
            with: replacement
        )
        return mutable as String
    }

    private static func nodeMatch(
        named wantedName: String,
        in source: String
    ) -> NSTextCheckingResult? {
        let pattern =
            #"\\node\s*(?:\[([^\]]*)\]\s*)?\(([^\)]+)\)\s*at\s*\((-?[0-9.]+)\s*,\s*(-?[0-9.]+)\)\s*\{([^{}]*)\}\s*;"#
        guard
            let regex = try? NSRegularExpression(
                pattern: pattern
            )
        else {
            return nil
        }

        let nsSource = source as NSString
        let range = NSRange(
            location: 0,
            length: nsSource.length
        )
        return regex
            .matches(
                in: source,
                range: range
            )
            .first {
                $0.numberOfRanges == 6
                    && nsSource.substring(
                        with: $0.range(at: 2)
                    ) == wantedName
            }
    }

    private static func edgeMatch(
        edgeID: String,
        in source: String
    ) -> NSTextCheckingResult? {
        guard
            let target = TikZGraphParser
                .parseEdges(source)
                .first(
                    where: {
                        $0.id == edgeID
                    }
                )
        else {
            return nil
        }

        let pattern =
            #"\\draw\s*(?:\[((?:[^\[\]]|\[[^\]]*\])*)\])?\s*\("#
            + NSRegularExpression
                .escapedPattern(
                    for: target.source
                )
            + #"\)\s*--\s*(?:node(?:\[[^\]]*\])?\s*\{([^{}]*)\}\s*)?\("#
            + NSRegularExpression
                .escapedPattern(
                    for: target.target
                )
            + #"\)\s*;"#

        guard
            let regex = try? NSRegularExpression(
                pattern: pattern
            )
        else {
            return nil
        }

        let nsSource = source as NSString
        let range = NSRange(
            location: 0,
            length: nsSource.length
        )
        let occurrence = Int(
            edgeID
                .split(separator: "#")
                .last
                ?? "0"
        ) ?? 0
        let matches = regex.matches(
            in: source,
            range: range
        )
        guard
            occurrence < matches.count
        else {
            return nil
        }
        return matches[occurrence]
    }

    private static func moveNodeCommand(
        named name: String,
        in source: String,
        toFront: Bool
    ) -> String {
        guard
            let match = nodeMatch(
                named: name,
                in: source
            )
        else {
            return source
        }

        let nsSource = source as NSString
        let command = nsSource.substring(
            with: match.range(at: 0)
        )
        let mutable = NSMutableString(
            string: source
        )
        mutable.deleteCharacters(
            in: match.range(at: 0)
        )
        let reduced = mutable as String

        let insertionRange: NSRange
        if toFront {
            insertionRange = firstEdgeRange(
                in: reduced
            ) ?? endPictureRange(
                in: reduced
            )
        } else {
            insertionRange = firstNodeRange(
                in: reduced
            ) ?? firstEdgeRange(
                in: reduced
            ) ?? endPictureRange(
                in: reduced
            )
        }

        let result = NSMutableString(
            string: reduced
        )
        result.insert(
            command + "\n",
            at: insertionRange.location
        )
        return normalizeBlankLines(
            result as String
        )
    }

    private static func moveEdgeCommand(
        edgeID: String,
        in source: String,
        toFront: Bool
    ) -> String {
        guard
            let match = edgeMatch(
                edgeID: edgeID,
                in: source
            )
        else {
            return source
        }

        let nsSource = source as NSString
        let command = nsSource.substring(
            with: match.range(at: 0)
        )
        let mutable = NSMutableString(
            string: source
        )
        mutable.deleteCharacters(
            in: match.range(at: 0)
        )
        let reduced = mutable as String

        let insertionRange = toFront
            ? endPictureRange(
                in: reduced
            )
            : (
                firstEdgeRange(
                    in: reduced
                )
                    ?? endPictureRange(
                        in: reduced
                    )
            )

        let result = NSMutableString(
            string: reduced
        )
        result.insert(
            command + "\n",
            at: insertionRange.location
        )
        return normalizeBlankLines(
            result as String
        )
    }

    private static func firstNodeRange(
        in source: String
    ) -> NSRange? {
        firstRange(
            pattern: #"\\node\b"#,
            in: source
        )
    }

    private static func firstEdgeRange(
        in source: String
    ) -> NSRange? {
        firstRange(
            pattern: #"\\draw\b"#,
            in: source
        )
    }

    private static func endPictureRange(
        in source: String
    ) -> NSRange {
        firstRange(
            pattern: #"\\end\{tikzpicture\}"#,
            in: source
        ) ?? NSRange(
            location: (source as NSString).length,
            length: 0
        )
    }

    private static func firstRange(
        pattern: String,
        in source: String
    ) -> NSRange? {
        guard
            let regex = try? NSRegularExpression(
                pattern: pattern
            )
        else {
            return nil
        }
        let nsSource = source as NSString
        return regex
            .firstMatch(
                in: source,
                range: NSRange(
                    location: 0,
                    length: nsSource.length
                )
            )?
            .range(at: 0)
    }

    private static func edgeLabelPart(
        _ label: String,
        textColor: TikZColorValue
    ) -> String {
        label
            .trimmingCharacters(
                in: .whitespacesAndNewlines
            )
            .isEmpty
            ? ""
            : " node[midway, fill=white, inner sep=1pt, text=\(textColor.tikzValue)] {\(escape(label))}"
    }

    private static func nextNodeName(
        in source: String
    ) -> String {
        let pattern =
            #"\(ndNode([0-9]+)\)"#
        guard
            let regex = try? NSRegularExpression(
                pattern: pattern
            )
        else {
            return "ndNode1"
        }

        let nsSource = source as NSString
        let range = NSRange(
            location: 0,
            length: nsSource.length
        )
        let maximum = regex
            .matches(
                in: source,
                range: range
            )
            .compactMap {
                match -> Int?
                in
                guard
                    match.numberOfRanges > 1
                else {
                    return nil
                }
                return Int(
                    nsSource.substring(
                        with: match.range(
                            at: 1
                        )
                    )
                )
            }
            .max()
            ?? 0
        return "ndNode\(maximum + 1)"
    }

    private static func normalizeBlankLines(
        _ source: String
    ) -> String {
        var result = source
        while result.contains("\n\n\n") {
            result = result.replacingOccurrences(
                of: "\n\n\n",
                with: "\n\n"
            )
        }
        return result
    }

    private static func escape(
        _ text: String
    ) -> String {
        text
            .map {
                character -> String
                in
                switch character {
                case "\\":
                    return "\\textbackslash{}"
                case "&":
                    return "\\&"
                case "%":
                    return "\\%"
                case "$":
                    return "\\$"
                case "#":
                    return "\\#"
                case "_":
                    return "\\_"
                case "{":
                    return "\\{"
                case "}":
                    return "\\}"
                default:
                    return String(character)
                }
            }
            .joined()
    }
}
