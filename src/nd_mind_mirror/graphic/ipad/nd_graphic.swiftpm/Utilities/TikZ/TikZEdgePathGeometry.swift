// Shared route geometry for drawing, hit testing, labels, and selection handles.

import CoreGraphics

struct TikZEdgeRoute {
    let start: CGPoint
    let end: CGPoint
    let firstControl: CGPoint?
    let secondControl: CGPoint?
    let bendPoints: [CGPoint]
    let sampledPoints: [CGPoint]

    var labelPoint: CGPoint {
        TikZEdgePathGeometry.midpoint(
            along: sampledPoints
        )
    }

    var arrowDirectionStart: CGPoint {
        if let last = sampledPoints.dropLast().last {
            return last
        }
        return start
    }
}

struct TikZEdgePathGeometry {
    private let mapper = TikZCoordinateMapper()
    private let nodeGeometry = TikZNodeGeometry()

    func route(
        for edge: TikZEdge,
        sourceNode: TikZNode,
        targetNode: TikZNode,
        in canvasSize: CGSize
    ) -> TikZEdgeRoute {
        let sourceCenter = mapper.viewPoint(
            for: sourceNode.position,
            in: canvasSize
        )
        let targetCenter = mapper.viewPoint(
            for: targetNode.position,
            in: canvasSize
        )

        switch edge.geometry.kind {
        case .straight:
            let endpoints = nodeGeometry.connectorEndpoints(
                from: sourceNode,
                to: targetNode,
                in: canvasSize
            )
            return TikZEdgeRoute(
                start: endpoints.start,
                end: endpoints.end,
                firstControl: nil,
                secondControl: nil,
                bendPoints: [],
                sampledPoints: [
                    endpoints.start,
                    endpoints.end
                ]
            )

        case .curve:
            let defaultGeometry =
                TikZConnectorGeometry.initial(
                    kind: .curve,
                    source: sourceNode.position,
                    target: targetNode.position
                )
            let firstTikZ =
                edge.geometry.firstControl
                ?? defaultGeometry.firstControl
                ?? sourceNode.position
            let secondTikZ =
                edge.geometry.secondControl
                ?? defaultGeometry.secondControl
                ?? targetNode.position
            let first = mapper.viewPoint(
                for: firstTikZ,
                in: canvasSize
            )
            let second = mapper.viewPoint(
                for: secondTikZ,
                in: canvasSize
            )
            let start = nodeGeometry.boundaryPoint(
                for: sourceNode,
                toward: first,
                in: canvasSize
            )
            let end = nodeGeometry.boundaryPoint(
                for: targetNode,
                toward: second,
                in: canvasSize
            )
            return TikZEdgeRoute(
                start: start,
                end: end,
                firstControl: first,
                secondControl: second,
                bendPoints: [],
                sampledPoints: sampleCubic(
                    start: start,
                    first: first,
                    second: second,
                    end: end
                )
            )

        case .polyline:
            let bends = edge.geometry
                .bendPoints
                .map {
                    mapper.viewPoint(
                        for: $0,
                        in: canvasSize
                    )
                }
            let firstTarget =
                bends.first
                ?? targetCenter
            let lastTarget =
                bends.last
                ?? sourceCenter
            let start = nodeGeometry.boundaryPoint(
                for: sourceNode,
                toward: firstTarget,
                in: canvasSize
            )
            let end = nodeGeometry.boundaryPoint(
                for: targetNode,
                toward: lastTarget,
                in: canvasSize
            )
            return TikZEdgeRoute(
                start: start,
                end: end,
                firstControl: nil,
                secondControl: nil,
                bendPoints: bends,
                sampledPoints:
                    [start]
                    + bends
                    + [end]
            )
        }
    }

    func distance(
        from point: CGPoint,
        to edge: TikZEdge,
        sourceNode: TikZNode,
        targetNode: TikZNode,
        in canvasSize: CGSize
    ) -> CGFloat {
        let points = route(
            for: edge,
            sourceNode: sourceNode,
            targetNode: targetNode,
            in: canvasSize
        ).sampledPoints

        guard points.count > 1 else {
            return .greatestFiniteMagnitude
        }

        var result = CGFloat.greatestFiniteMagnitude
        for index in 0..<(points.count - 1) {
            let candidate = distance(
                from: point,
                toSegmentFrom: points[index],
                to: points[index + 1]
            )
            if candidate < result {
                result = candidate
            }
        }
        return result
    }

    func nearestSegmentIndex(
        to point: CGPoint,
        edge: TikZEdge,
        sourceNode: TikZNode,
        targetNode: TikZNode,
        in canvasSize: CGSize
    ) -> Int {
        let points = route(
            for: edge,
            sourceNode: sourceNode,
            targetNode: targetNode,
            in: canvasSize
        ).sampledPoints
        guard points.count > 1 else {
            return 0
        }

        var bestIndex = 0
        var bestDistance = CGFloat.greatestFiniteMagnitude
        for index in 0..<(points.count - 1) {
            let candidate = distance(
                from: point,
                toSegmentFrom: points[index],
                to: points[index + 1]
            )
            if candidate < bestDistance {
                bestDistance = candidate
                bestIndex = index
            }
        }
        return bestIndex
    }

    private func sampleCubic(
        start: CGPoint,
        first: CGPoint,
        second: CGPoint,
        end: CGPoint
    ) -> [CGPoint] {
        let steps = 28
        var points: [CGPoint] = []
        points.reserveCapacity(steps + 1)

        for step in 0...steps {
            let t = CGFloat(step) / CGFloat(steps)
            points.append(
                cubicPoint(
                    start: start,
                    first: first,
                    second: second,
                    end: end,
                    t: t
                )
            )
        }
        return points
    }

    private func cubicPoint(
        start: CGPoint,
        first: CGPoint,
        second: CGPoint,
        end: CGPoint,
        t: CGFloat
    ) -> CGPoint {
        let u = 1.0 - t
        let uu = u * u
        let tt = t * t
        let startWeight = uu * u
        let firstWeight = 3.0 * uu * t
        let secondWeight = 3.0 * u * tt
        let endWeight = tt * t

        let x = weightedCoordinate(
            start: start.x,
            first: first.x,
            second: second.x,
            end: end.x,
            startWeight: startWeight,
            firstWeight: firstWeight,
            secondWeight: secondWeight,
            endWeight: endWeight
        )
        let y = weightedCoordinate(
            start: start.y,
            first: first.y,
            second: second.y,
            end: end.y,
            startWeight: startWeight,
            firstWeight: firstWeight,
            secondWeight: secondWeight,
            endWeight: endWeight
        )
        return CGPoint(x: x, y: y)
    }

    private func weightedCoordinate(
        start: CGFloat,
        first: CGFloat,
        second: CGFloat,
        end: CGFloat,
        startWeight: CGFloat,
        firstWeight: CGFloat,
        secondWeight: CGFloat,
        endWeight: CGFloat
    ) -> CGFloat {
        let startPart = startWeight * start
        let firstPart = firstWeight * first
        let secondPart = secondWeight * second
        let endPart = endWeight * end
        return startPart + firstPart + secondPart + endPart
    }

    private func distance(
        from point: CGPoint,
        toSegmentFrom start: CGPoint,
        to end: CGPoint
    ) -> CGFloat {
        let dx = end.x - start.x
        let dy = end.y - start.y
        let lengthSquared = dx * dx + dy * dy

        guard lengthSquared > 0.0001 else {
            let pointDX = point.x - start.x
            let pointDY = point.y - start.y
            return hypot(pointDX, pointDY)
        }

        let relativeX = point.x - start.x
        let relativeY = point.y - start.y
        let dot = relativeX * dx + relativeY * dy
        let projection = dot / lengthSquared
        let t = min(max(projection, 0.0), 1.0)
        let closestX = start.x + t * dx
        let closestY = start.y + t * dy
        let pointDX = point.x - closestX
        let pointDY = point.y - closestY
        return hypot(pointDX, pointDY)
    }

    static func midpoint(
        along points: [CGPoint]
    ) -> CGPoint {
        guard let first = points.first else {
            return .zero
        }
        guard points.count > 1 else {
            return first
        }

        var lengths: [CGFloat] = []
        lengths.reserveCapacity(points.count - 1)
        var total: CGFloat = 0.0

        for index in 0..<(points.count - 1) {
            let start = points[index]
            let end = points[index + 1]
            let dx = end.x - start.x
            let dy = end.y - start.y
            let length = hypot(dx, dy)
            lengths.append(length)
            total += length
        }

        let wanted = total / 2.0
        var walked: CGFloat = 0.0

        for index in lengths.indices {
            let length = lengths[index]
            let next = walked + length
            if next >= wanted {
                let safeLength = max(length, 0.0001)
                let ratio = (wanted - walked) / safeLength
                let start = points[index]
                let end = points[index + 1]
                let dx = end.x - start.x
                let dy = end.y - start.y
                return CGPoint(
                    x: start.x + dx * ratio,
                    y: start.y + dy * ratio
                )
            }
            walked = next
        }

        return points.last ?? first
    }
}
