// Source-preserving TikZ edits for named nodes and editable connector routes.

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
        applyNodeStyle(
            style,
            to: &options
        )
        options.setFlag(
            shape.rawValue,
            enabled: true
        )
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

        return appending(
            command: command,
            to: prepared
        )
    }

    static func moveNode(
        named name: String,
        to point: CGPoint,
        in source: String
    ) -> String {
        replacingNode(
            named: name,
            in: source
        ) {
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
        replacingNode(
            named: name,
            in: source
        ) {
            rawOptions,
            nodeName,
            _,
            _,
            label
            in
            var options = TikZOptionList(
                rawOptions
            )
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
        replacingNode(
            named: name,
            in: source
        ) {
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
        replacingNode(
            named: name,
            in: source
        ) {
            rawOptions,
            nodeName,
            x,
            y,
            label
            in
            var options = TikZOptionList(
                rawOptions
            )
            applyNodeStyle(
                style,
                to: &options
            )
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
                .first(
                    where: {
                        $0.name == name
                    }
                )
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
        ) {
            _,
            _,
            _,
            _,
            _
            in
            ""
        }

        return normalizeBlankLines(
            result
        )
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
        geometry: TikZConnectorGeometry = .straight,
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
        applyEdgeStyle(
            style,
            to: &options
        )

        return appending(
            command: edgeCommand(
                sourceNode: sourceNode,
                targetNode: targetNode,
                label: label,
                labelTextColor: style.textColor,
                options: options,
                geometry: geometry
            ),
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
            rawOptions,
            edge
            in
            var options = TikZOptionList(
                rawOptions
            )
            applyEdgeStyle(
                style,
                to: &options
            )
            return edgeCommand(
                sourceNode: edge.source,
                targetNode: edge.target,
                label: label,
                labelTextColor: style.textColor,
                options: options,
                geometry: edge.geometry
            )
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
            edge
            in
            var options = TikZOptionList(
                rawOptions
            )
            applyEdgeStyle(
                style,
                to: &options
            )
            return edgeCommand(
                sourceNode: edge.source,
                targetNode: edge.target,
                label: edge.label,
                labelTextColor: style.textColor,
                options: options,
                geometry: edge.geometry
            )
        }
    }

    static func updateEdgeGeometry(
        edgeID: String,
        geometry: TikZConnectorGeometry,
        in source: String
    ) -> String {
        replacingEdge(
            edgeID: edgeID,
            in: source
        ) {
            rawOptions,
            edge
            in
            edgeCommand(
                sourceNode: edge.source,
                targetNode: edge.target,
                label: edge.label,
                labelTextColor: edge.textColor,
                options: TikZOptionList(
                    rawOptions
                ),
                geometry: geometry
            )
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
            ) {
                _,
                _
                in
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
                    let point = positions[
                        name
                    ]
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
            let prefix = source[
                ..<range.lowerBound
            ].hasSuffix("\n")
                ? ""
                : "\n"
            result.insert(
                contentsOf:
                    prefix
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
            + (
                source.hasSuffix("\n")
                ? ""
                : "\n"
            )
            + command
            + "\n"
    }

    private static func edgeCommand(
        sourceNode: String,
        targetNode: String,
        label: String,
        labelTextColor: TikZColorValue,
        options: TikZOptionList,
        geometry: TikZConnectorGeometry
    ) -> String {
        let labelPart = edgeLabelPart(
            label,
            textColor: labelTextColor
        )
        let prefix =
            "\\draw"
            + (
                options.serialized.isEmpty
                ? ""
                : "[\(options.serialized)]"
            )
            + " (\(sourceNode))"

        switch geometry.kind {
        case .straight:
            return prefix
                + " --\(labelPart) "
                + "(\(targetNode));"

        case .curve:
            guard
                let first = geometry.firstControl,
                let second = geometry.secondControl
            else {
                return prefix
                    + " --\(labelPart) "
                    + "(\(targetNode));"
            }
            return prefix
                + " .. controls "
                + coordinate(first)
                + " and "
                + coordinate(second)
                + " ..\(labelPart) "
                + "(\(targetNode));"

        case .polyline:
            let bends = geometry
                .bendPoints
                .map {
                    " -- \(coordinate($0))"
                }
                .joined()
            return prefix
                + bends
                + " --\(labelPart) "
                + "(\(targetNode));"
        }
    }

    private static func edgeLabelPart(
        _ label: String,
        textColor: TikZColorValue
    ) -> String {
        guard !label.isEmpty else {
            return ""
        }
        return " node[midway, fill=white, inner sep=1pt, text=\(textColor.tikzValue)] "
            + "{\(escape(label))}"
    }

    private static func coordinate(
        _ point: CGPoint
    ) -> String {
        "(\(mapper.number(Double(point.x))),\(mapper.number(Double(point.y))))"
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
            enabled:
                style.linePattern
                == .dashed
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

        let nsSource = source
            as NSString
        let options = capture(
            match,
            index: 1,
            source: nsSource
        )
        let replacement = transform(
            options,
            capture(
                match,
                index: 2,
                source: nsSource
            ),
            capture(
                match,
                index: 3,
                source: nsSource
            ),
            capture(
                match,
                index: 4,
                source: nsSource
            ),
            capture(
                match,
                index: 5,
                source: nsSource
            )
        )

        return replacing(
            match.range(at: 0),
            with: replacement,
            in: source
        )
    }

    private static func replacingEdge(
        edgeID: String,
        in source: String,
        transform: (
            _ options: String,
            _ edge: TikZEdge
        ) -> String
    ) -> String {
        guard
            let edge = TikZGraphParser
                .parseEdges(source)
                .first(
                    where: {
                        $0.id == edgeID
                    }
                ),
            let match = edgeMatch(
                edgeID: edgeID,
                in: source
            )
        else {
            return source
        }

        let nsSource = source
            as NSString
        let rawOptions = capture(
            match,
            index: 1,
            source: nsSource
        )
        return replacing(
            match.range(at: 0),
            with: transform(
                rawOptions,
                edge
            ),
            in: source
        )
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

        let nsSource = source
            as NSString
        return regex
            .matches(
                in: source,
                range: NSRange(
                    location: 0,
                    length:
                        nsSource.length
                )
            )
            .first {
                capture(
                    $0,
                    index: 2,
                    source: nsSource
                ) == wantedName
            }
    }

    private static func edgeMatch(
        edgeID: String,
        in source: String
    ) -> NSTextCheckingResult? {
        guard
            let regex = try? NSRegularExpression(
                pattern:
                    TikZGraphParser
                    .edgeCommandPattern,
                options:
                    [.dotMatchesLineSeparators]
            )
        else {
            return nil
        }

        let nsSource = source
            as NSString
        var counts: [String: Int] =
            [:]

        for match in regex.matches(
            in: source,
            range: NSRange(
                location: 0,
                length:
                    nsSource.length
            )
        ) {
            let sourceName = capture(
                match,
                index: 2,
                source: nsSource
            )
            let targetName = capture(
                match,
                index: 4,
                source: nsSource
            )
            let base =
                "\(sourceName)->\(targetName)"
            let occurrence = counts[
                base,
                default: 0
            ]
            counts[base] =
                occurrence + 1
            if "\(base)#\(occurrence)"
                == edgeID
            {
                return match
            }
        }
        return nil
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
        return moveCommand(
            match.range(at: 0),
            in: source,
            toFront: toFront
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
        return moveCommand(
            match.range(at: 0),
            in: source,
            toFront: toFront
        )
    }

    private static func moveCommand(
        _ range: NSRange,
        in source: String,
        toFront: Bool
    ) -> String {
        let nsSource = source
            as NSString
        let command = nsSource
            .substring(
                with: range
            )
            .trimmingCharacters(
                in:
                    .whitespacesAndNewlines
            )
        var result = replacing(
            range,
            with: "",
            in: source
        )
        result = normalizeBlankLines(
            result
        )

        if toFront {
            return appending(
                command: command,
                to: result
            )
        }

        let begin =
            "\\begin{tikzpicture}"
        guard
            let beginRange = result
                .range(
                    of: begin
                )
        else {
            return appending(
                command: command,
                to: result
            )
        }

        var moved = result
        moved.insert(
            contentsOf:
                "\n    \(command)",
            at:
                beginRange
                .upperBound
        )
        return normalizeBlankLines(
            moved
        )
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
        let maximum = regex
            .matches(
                in: source,
                range: NSRange(
                    location: 0,
                    length: nsSource.length
                )
            )
            .compactMap {
                match -> Int? in
                guard
                    match.numberOfRanges > 1
                else {
                    return nil
                }
                return Int(
                    nsSource.substring(
                        with: match.range(at: 1)
                    )
                )
            }
            .max()
            ?? 0
        return "ndNode\(maximum + 1)"
    }

    private static func replacing(
        _ range: NSRange,
        with replacement: String,
        in source: String
    ) -> String {
        let mutable =
            NSMutableString(
                string: source
            )
        mutable.replaceCharacters(
            in: range,
            with: replacement
        )
        return mutable
            as String
    }

    private static func capture(
        _ match: NSTextCheckingResult,
        index: Int,
        source: NSString
    ) -> String {
        let range = match.range(
            at: index
        )
        guard
            range.location
                != NSNotFound
        else {
            return ""
        }
        return source.substring(
            with: range
        )
    }

    private static func escape(
        _ text: String
    ) -> String {
        var result = ""
        var escaping = false

        for character in text {
            if escaping {
                result.append(character)
                escaping = false
                continue
            }
            if character == "\\" {
                result.append(character)
                escaping = true
                continue
            }
            switch character {
            case "_", "%", "#", "&", "$":
                result.append("\\")
                result.append(character)
            default:
                result.append(character)
            }
        }
        return result
    }

    private static func normalizeBlankLines(
        _ source: String
    ) -> String {
        source.replacingOccurrences(
            of: #"\n[ \t]*\n[ \t]*\n+"#,
            with: "\n\n",
            options:
                .regularExpression
        )
    }
}
