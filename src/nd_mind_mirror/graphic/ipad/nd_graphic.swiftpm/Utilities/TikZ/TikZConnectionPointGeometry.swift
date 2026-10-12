// Equal-perimeter connection points for rectangle and ellipse TikZ nodes.

import CoreGraphics

struct TikZConnectionPointGeometry {
    private let nodeGeometry = TikZNodeGeometry()

    func points(
        for node: TikZNode,
        count: Int,
        in canvasSize: CGSize
    ) -> [CGPoint] {
        let count = max(count, TikZConnectionPointMetadata.defaultCount)
        let rect = nodeGeometry.rect(for: node, in: canvasSize)
        switch node.shape {
        case .ellipse, .circle:
            return ellipsePoints(in: rect, count: count)
        case .triangle:
            return trianglePoints(in: rect, count: count)
        case .rectangle:
            return rectanglePoints(in: rect, count: count)
        }
    }

    func nearest(
        to point: CGPoint,
        in graph: TikZGraph,
        counts: [String: Int],
        canvasSize: CGSize,
        excluding excludedName: String? = nil,
        tolerance: CGFloat = 26
    ) -> (node: TikZNode, index: Int, point: CGPoint)? {
        var best: (TikZNode, Int, CGPoint, CGFloat)?
        for node in graph.nodes.reversed() where node.name != excludedName {
            let candidates = points(
                for: node,
                count: counts[node.name] ?? TikZConnectionPointMetadata.defaultCount,
                in: canvasSize
            )
            for (index, candidate) in candidates.enumerated() {
                let distance = hypot(candidate.x - point.x, candidate.y - point.y)
                guard distance <= tolerance else { continue }
                if best == nil || distance < best!.3 {
                    best = (node, index, candidate, distance)
                }
            }
        }
        guard let best else { return nil }
        return (best.0, best.1, best.2)
    }

    private func rectanglePoints(
        in rect: CGRect,
        count: Int
    ) -> [CGPoint] {
        if count == 4 {
            return [
                CGPoint(x: rect.midX, y: rect.minY),
                CGPoint(x: rect.maxX, y: rect.midY),
                CGPoint(x: rect.midX, y: rect.maxY),
                CGPoint(x: rect.minX, y: rect.midY),
            ]
        }

        let perimeter = max(2 * (rect.width + rect.height), 1)
        let start = rect.width / 2
        return (0..<count).map { index in
            pointOnRectangle(
                rect,
                distance: start + perimeter * CGFloat(index) / CGFloat(count)
            )
        }
    }

    private func pointOnRectangle(
        _ rect: CGRect,
        distance rawDistance: CGFloat
    ) -> CGPoint {
        let perimeter = max(2 * (rect.width + rect.height), 1)
        var distance = rawDistance.truncatingRemainder(dividingBy: perimeter)
        if distance < rect.width {
            return CGPoint(x: rect.minX + distance, y: rect.minY)
        }
        distance -= rect.width
        if distance < rect.height {
            return CGPoint(x: rect.maxX, y: rect.minY + distance)
        }
        distance -= rect.height
        if distance < rect.width {
            return CGPoint(x: rect.maxX - distance, y: rect.maxY)
        }
        distance -= rect.width
        return CGPoint(x: rect.minX, y: rect.maxY - distance)
    }

    private func trianglePoints(
        in rect: CGRect,
        count: Int
    ) -> [CGPoint] {
        let vertices = [
            CGPoint(x: rect.midX, y: rect.minY),
            CGPoint(x: rect.maxX, y: rect.maxY),
            CGPoint(x: rect.minX, y: rect.maxY),
        ]
        let sides: [CGFloat] = (0..<3).map { index in
            let start = vertices[index]
            let end = vertices[(index + 1) % 3]
            return hypot(end.x - start.x, end.y - start.y)
        }
        let perimeter = sides.reduce(0, +)
        guard perimeter > 0 else { return vertices }
        return (0..<count).map { index in
            var distance = perimeter * CGFloat(index) / CGFloat(count)
            for side in 0..<3 {
                if distance <= sides[side] || side == 2 {
                    let start = vertices[side]
                    let end = vertices[(side + 1) % 3]
                    let fraction = min(max(distance / max(sides[side], 1), 0), 1)
                    return CGPoint(
                        x: start.x + fraction * (end.x - start.x),
                        y: start.y + fraction * (end.y - start.y)
                    )
                }
                distance -= sides[side]
            }
            return vertices[0]
        }
    }

    private func ellipsePoints(
        in rect: CGRect,
        count: Int
    ) -> [CGPoint] {
        let samples = max(256, count * 32)
        var sampled: [CGPoint] = []
        sampled.reserveCapacity(samples + 1)
        for index in 0...samples {
            let angle = -Double.pi / 2
                + 2 * Double.pi * Double(index) / Double(samples)
            sampled.append(
                CGPoint(
                    x: rect.midX + rect.width / 2 * CGFloat(cos(angle)),
                    y: rect.midY + rect.height / 2 * CGFloat(sin(angle))
                )
            )
        }

        var cumulative: [CGFloat] = [0]
        for index in 1..<sampled.count {
            let previous = sampled[index - 1]
            let current = sampled[index]
            cumulative.append(
                cumulative[index - 1]
                    + hypot(current.x - previous.x, current.y - previous.y)
            )
        }
        let total = max(cumulative.last ?? 1, 1)

        return (0..<count).map { index in
            let wanted = total * CGFloat(index) / CGFloat(count)
            let upper = cumulative.firstIndex(where: { $0 >= wanted }) ?? (cumulative.count - 1)
            guard upper > 0 else { return sampled[0] }
            let lower = upper - 1
            let span = max(cumulative[upper] - cumulative[lower], 0.0001)
            let ratio = (wanted - cumulative[lower]) / span
            return CGPoint(
                x: sampled[lower].x + (sampled[upper].x - sampled[lower].x) * ratio,
                y: sampled[lower].y + (sampled[upper].y - sampled[lower].y) * ratio
            )
        }
    }
}
