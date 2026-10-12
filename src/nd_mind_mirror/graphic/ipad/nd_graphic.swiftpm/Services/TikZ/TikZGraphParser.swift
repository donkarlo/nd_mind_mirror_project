// Parse the conservative named-node and named-edge TikZ subset used by the visual editor.

import CoreGraphics
import Foundation

enum TikZGraphParser {
    private static let coordinatePattern =
        #"\(\s*(-?[0-9.]+)\s*,\s*(-?[0-9.]+)\s*\)"#

    static func parse(_ source: String) -> TikZGraph {
        TikZGraph(
            nodes: parseNodes(source),
            edges: parseEdges(source)
        )
    }

    static func parseNodes(_ source: String) -> [TikZNode] {
        let pattern =
            #"\\node\s*(?:\[([^\]]*)\]\s*)?\(([^\)]+)\)\s*at\s*\((-?[0-9.]+)\s*,\s*(-?[0-9.]+)\)\s*\{([^{}]*)\}\s*;"#
        guard
            let regex = try? NSRegularExpression(
                pattern: pattern
            )
        else {
            return []
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
            .compactMap { match in
                guard
                    match.numberOfRanges == 6,
                    let x = Double(
                        nsSource.substring(
                            with: match.range(at: 3)
                        )
                    ),
                    let y = Double(
                        nsSource.substring(
                            with: match.range(at: 4)
                        )
                    )
                else {
                    return nil
                }

                let rawOptions =
                    match.range(at: 1).location == NSNotFound
                    ? ""
                    : nsSource.substring(
                        with: match.range(at: 1)
                    )
                let options = TikZOptionList(
                    rawOptions
                )
                let name = nsSource.substring(
                    with: match.range(at: 2)
                )
                let label = nsSource.substring(
                    with: match.range(at: 5)
                )
                let shape: TikZNodeShape
                if options.containsFlag("regular polygon")
                    && options.value(for: "regular polygon sides") == "3" {
                    shape = .triangle
                } else if options.containsFlag("circle") {
                    shape = .circle
                } else if options.containsFlag("ellipse") {
                    shape = .ellipse
                } else {
                    shape = .rectangle
                }

                let rawWidth = optionMeasurement(
                    "minimum width",
                    options: options
                ) ?? (shape == .circle ? 1.5 : shape == .ellipse ? 1.8 : 2.0)
                let rawHeight = optionMeasurement(
                    "minimum height",
                    options: options
                ) ?? (shape == .circle ? 1.5 : shape == .ellipse ? 1.1 : 1.0)
                let diameter = max(rawWidth, rawHeight)

                return TikZNode(
                    name: name,
                    label: label,
                    position: CGPoint(
                        x: x,
                        y: y
                    ),
                    width: shape == .circle ? diameter : rawWidth,
                    height: shape == .circle ? diameter : rawHeight,
                    shape: shape,
                    fillColor:
                        TikZColorValue.fromTikZ(
                            options.value(for: "fill")
                        )
                        ?? .white,
                    strokeColor:
                        TikZColorValue.fromTikZ(
                            options.value(for: "draw")
                        )
                        ?? .black,
                    textColor:
                        TikZColorValue.fromTikZ(
                            options.value(for: "text")
                        )
                        ?? .black,
                    lineWidth:
                        optionMeasurement(
                            "line width",
                            options: options
                        )
                        ?? 1.0
                )
            }
    }

    static func parseEdges(_ source: String) -> [TikZEdge] {
        guard
            let regex = try? NSRegularExpression(
                pattern: edgeCommandPattern,
                options: [.dotMatchesLineSeparators]
            )
        else {
            return []
        }

        let nsSource = source as NSString
        let range = NSRange(
            location: 0,
            length: nsSource.length
        )
        var counts: [String: Int] = [:]

        return regex
            .matches(
                in: source,
                range: range
            )
            .compactMap { match in
                guard match.numberOfRanges == 5 else {
                    return nil
                }

                let rawOptions = capture(
                    match,
                    index: 1,
                    source: nsSource
                )
                let sourceName = capture(
                    match,
                    index: 2,
                    source: nsSource
                )
                let pathBody = capture(
                    match,
                    index: 3,
                    source: nsSource
                )
                let targetName = capture(
                    match,
                    index: 4,
                    source: nsSource
                )

                guard
                    !sourceName.isEmpty,
                    !targetName.isEmpty
                else {
                    return nil
                }

                let options = TikZOptionList(
                    rawOptions
                )
                let labelInfo = parseLabel(
                    from: pathBody
                )
                let base = "\(sourceName)->\(targetName)"
                let occurrence = counts[
                    base,
                    default: 0
                ]
                counts[base] = occurrence + 1

                let directed =
                    options.containsFlag("->")
                    || rawOptions.contains("-{Latex}")
                    || rawOptions
                        .localizedCaseInsensitiveContains(
                            "latex"
                        )
                let arrowHeadStyle:
                    TikZArrowHeadStyle =
                    rawOptions.contains(
                        "Latex[open]"
                    )
                    ? .open
                    : .filled

                return TikZEdge(
                    id: "\(base)#\(occurrence)",
                    source: sourceName,
                    target: targetName,
                    label: labelInfo.label,
                    directed: directed,
                    strokeColor:
                        TikZColorValue.fromTikZ(
                            options.value(for: "draw")
                        )
                        ?? .black,
                    textColor:
                        TikZColorValue.fromTikZ(
                            labelInfo.options
                                .value(for: "text")
                        )
                        ?? .black,
                    lineWidth:
                        optionMeasurement(
                            "line width",
                            options: options
                        )
                        ?? 1.0,
                    linePattern:
                        options.containsFlag("dashed")
                        ? .dashed
                        : .solid,
                    arrowHeadStyle:
                        arrowHeadStyle,
                    geometry:
                        parseGeometry(
                            from: pathBody
                        )
                )
            }
    }

    static var edgeCommandPattern: String {
        #"\\draw\s*(?:\[((?:[^\[\]]|\[[^\]]*\])*)\])?\s*\(([^\)]+)\)\s*(.*?)\s*\(([^\)]+)\)\s*;"#
    }

    private static func parseGeometry(
        from pathBody: String
    ) -> TikZConnectorGeometry {
        if let controls = parseCurveControls(
            from: pathBody
        ) {
            return TikZConnectorGeometry(
                kind: .curve,
                firstControl: controls.first,
                secondControl: controls.second,
                bendPoints: []
            )
        }

        let bends = parsePolylineBends(
            from: pathBody
        )
        if !bends.isEmpty {
            return TikZConnectorGeometry(
                kind: .polyline,
                firstControl: nil,
                secondControl: nil,
                bendPoints: bends
            )
        }

        return .straight
    }

    private static func parseCurveControls(
        from pathBody: String
    ) -> (
        first: CGPoint,
        second: CGPoint
    )? {
        let pattern =
            #"\.\.\s*controls\s*"# +
            coordinatePattern +
            #"\s*and\s*"# +
            coordinatePattern +
            #"\s*\.\."#

        guard
            let regex = try? NSRegularExpression(
                pattern: pattern
            ),
            let match = regex.firstMatch(
                in: pathBody,
                range: NSRange(
                    location: 0,
                    length: (
                        pathBody
                        as NSString
                    ).length
                )
            ),
            match.numberOfRanges == 5
        else {
            return nil
        }

        let nsBody = pathBody as NSString
        guard
            let x1 = Double(
                nsBody.substring(
                    with: match.range(at: 1)
                )
            ),
            let y1 = Double(
                nsBody.substring(
                    with: match.range(at: 2)
                )
            ),
            let x2 = Double(
                nsBody.substring(
                    with: match.range(at: 3)
                )
            ),
            let y2 = Double(
                nsBody.substring(
                    with: match.range(at: 4)
                )
            )
        else {
            return nil
        }

        return (
            CGPoint(
                x: x1,
                y: y1
            ),
            CGPoint(
                x: x2,
                y: y2
            )
        )
    }

    private static func parsePolylineBends(
        from pathBody: String
    ) -> [CGPoint] {
        let pattern =
            #"--\s*"# +
            coordinatePattern
        guard
            let regex = try? NSRegularExpression(
                pattern: pattern
            )
        else {
            return []
        }

        let nsBody = pathBody as NSString
        let range = NSRange(
            location: 0,
            length: nsBody.length
        )

        return regex
            .matches(
                in: pathBody,
                range: range
            )
            .compactMap { match in
                guard
                    match.numberOfRanges == 3,
                    let x = Double(
                        nsBody.substring(
                            with: match.range(at: 1)
                        )
                    ),
                    let y = Double(
                        nsBody.substring(
                            with: match.range(at: 2)
                        )
                    )
                else {
                    return nil
                }
                return CGPoint(
                    x: x,
                    y: y
                )
            }
    }

    private static func parseLabel(
        from pathBody: String
    ) -> (
        label: String,
        options: TikZOptionList
    ) {
        let pattern =
            #"node(?:\[([^\]]*)\])?\s*\{([^{}]*)\}"#
        guard
            let regex = try? NSRegularExpression(
                pattern: pattern
            ),
            let match = regex.firstMatch(
                in: pathBody,
                range: NSRange(
                    location: 0,
                    length: (
                        pathBody
                        as NSString
                    ).length
                )
            ),
            match.numberOfRanges == 3
        else {
            return (
                "",
                TikZOptionList("")
            )
        }

        let nsBody = pathBody as NSString
        return (
            capture(
                match,
                index: 2,
                source: nsBody
            ),
            TikZOptionList(
                capture(
                    match,
                    index: 1,
                    source: nsBody
                )
            )
        )
    }

    private static func optionMeasurement(
        _ key: String,
        options: TikZOptionList
    ) -> Double? {
        guard
            let raw = options.value(
                for: key
            )
        else {
            return nil
        }

        let numeric = raw
            .replacingOccurrences(
                of: "cm",
                with: "",
                options: .caseInsensitive
            )
            .replacingOccurrences(
                of: "pt",
                with: "",
                options: .caseInsensitive
            )
            .trimmingCharacters(
                in: .whitespacesAndNewlines
            )
        return Double(
            numeric
        )
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
            range.location != NSNotFound
        else {
            return ""
        }
        return source.substring(
            with: range
        )
    }
}
