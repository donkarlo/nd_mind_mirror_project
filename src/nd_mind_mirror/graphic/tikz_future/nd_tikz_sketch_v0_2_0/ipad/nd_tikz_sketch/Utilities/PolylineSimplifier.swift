import CoreGraphics
import Foundation

enum PolylineSimplifier {
    static func simplify(_ points: [CGPoint], epsilon: CGFloat) -> [CGPoint] {
        guard points.count > 2 else { return points }
        let first = points[0]
        let last = points[points.count - 1]
        var index = 0
        var maxDistance: CGFloat = 0

        for candidateIndex in 1..<(points.count - 1) {
            let distance = perpendicularDistance(
                points[candidateIndex],
                lineStart: first,
                lineEnd: last
            )
            if distance > maxDistance {
                index = candidateIndex
                maxDistance = distance
            }
        }

        if maxDistance > epsilon {
            let left = simplify(Array(points[0...index]), epsilon: epsilon)
            let right = simplify(Array(points[index...]), epsilon: epsilon)
            return Array(left.dropLast()) + right
        }
        return [first, last]
    }

    private static func perpendicularDistance(
        _ point: CGPoint,
        lineStart: CGPoint,
        lineEnd: CGPoint
    ) -> CGFloat {
        let dx = lineEnd.x - lineStart.x
        let dy = lineEnd.y - lineStart.y
        if abs(dx) + abs(dy) < 0.0001 {
            return hypot(point.x - lineStart.x, point.y - lineStart.y)
        }
        let numerator = abs(
            dy * point.x - dx * point.y
            + lineEnd.x * lineStart.y
            - lineEnd.y * lineStart.x
        )
        return numerator / hypot(dx, dy)
    }
}
