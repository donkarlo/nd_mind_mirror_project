// Editable route geometry for TikZ connectors.

import CoreGraphics

struct TikZConnectorGeometry: Hashable {
    var kind: TikZConnectorKind
    var firstControl: CGPoint?
    var secondControl: CGPoint?
    var bendPoints: [CGPoint]

    static let straight = TikZConnectorGeometry(
        kind: .straight,
        firstControl: nil,
        secondControl: nil,
        bendPoints: []
    )

    static func initial(
        kind: TikZConnectorKind,
        source: CGPoint,
        target: CGPoint
    ) -> TikZConnectorGeometry {
        switch kind {
        case .straight:
            return .straight
        case .polyline:
            return TikZConnectorGeometry(
                kind: .polyline,
                firstControl: nil,
                secondControl: nil,
                bendPoints: [
                    clamp(
                        CGPoint(
                            x: (source.x + target.x) / 2,
                            y: (source.y + target.y) / 2
                        )
                    )
                ]
            )
        case .curve:
            let dx = target.x - source.x
            let dy = target.y - source.y
            let length = max(hypot(dx, dy), 0.001)
            let px = -dy / length
            let py = dx / length
            let lift = min(max(length * 0.22, 0.7), 2.0)

            return TikZConnectorGeometry(
                kind: .curve,
                firstControl: clamp(
                    CGPoint(
                        x: source.x + dx / 3 + px * lift,
                        y: source.y + dy / 3 + py * lift
                    )
                ),
                secondControl: clamp(
                    CGPoint(
                        x: source.x + dx * 2 / 3 + px * lift,
                        y: source.y + dy * 2 / 3 + py * lift
                    )
                ),
                bendPoints: []
            )
        }
    }

    mutating func setCurveControl(
        index: Int,
        point: CGPoint
    ) {
        guard kind == .curve else { return }
        if index == 0 {
            firstControl = Self.clamp(point)
        } else if index == 1 {
            secondControl = Self.clamp(point)
        }
    }

    mutating func setBendPoint(
        index: Int,
        point: CGPoint
    ) {
        guard kind == .polyline,
              bendPoints.indices.contains(index) else {
            return
        }
        bendPoints[index] = Self.clamp(point)
    }

    mutating func insertBendPoint(
        _ point: CGPoint,
        at index: Int
    ) {
        guard kind == .polyline else { return }
        let insertionIndex = min(
            max(index, 0),
            bendPoints.count
        )
        bendPoints.insert(
            Self.clamp(point),
            at: insertionIndex
        )
    }

    mutating func removeBendPoint(
        index: Int
    ) {
        guard kind == .polyline,
              bendPoints.indices.contains(index) else {
            return
        }
        bendPoints.remove(at: index)
    }

    private static func clamp(
        _ point: CGPoint
    ) -> CGPoint {
        CGPoint(
            x: min(max(point.x, 0), 16),
            y: min(max(point.y, 0), 11)
        )
    }
}
