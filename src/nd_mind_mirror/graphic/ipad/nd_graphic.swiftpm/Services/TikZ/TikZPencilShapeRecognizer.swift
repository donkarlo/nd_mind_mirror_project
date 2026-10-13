// Recognizes a closed Apple Pencil contour as a simple TikZ geometry.

import CoreGraphics
import Foundation

struct TikZPencilShapeRecognizer {
    struct Result {
        let shape: TikZNodeShape
        let bounds: CGRect
    }

    func recognize(_ samples: [CGPoint]) -> Result? {
        guard samples.count >= 12 else { return nil }
        let bounds = samples.reduce(CGRect.null) {
            $0.union(CGRect(origin: $1, size: .zero))
        }
        guard bounds.width >= 28, bounds.height >= 28 else { return nil }

        let diagonal = hypot(bounds.width, bounds.height)
        guard hypot(samples[0].x - samples[samples.count - 1].x,
                    samples[0].y - samples[samples.count - 1].y)
                <= max(20, diagonal * 0.24) else { return nil }

        let path = samples + [samples[0]]
        let length = zip(path.dropLast(), path.dropFirst()).reduce(CGFloat.zero) {
            sum, segment in
            sum + hypot(segment.0.x - segment.1.x,
                        segment.0.y - segment.1.y)
        }
        guard length >= (bounds.width + bounds.height) * 1.12 else { return nil }

        let center = CGPoint(x: bounds.midX, y: bounds.midY)
        let ellipseError = samples.reduce(CGFloat.zero) { sum, point in
            let x = (point.x - center.x) / (bounds.width / 2)
            let y = (point.y - center.y) / (bounds.height / 2)
            return sum + abs(sqrt(x * x + y * y) - 1)
        } / CGFloat(samples.count)

        if ellipseError < 0.115 {
            return Result(shape: .ellipse, bounds: bounds)
        }

        // Start near the upper-leftmost contour point so the simplification
        // retains the three or four main vertices independent of stroke start.
        let start = samples.indices.min { lhs, rhs in
            samples[lhs].x + samples[lhs].y < samples[rhs].x + samples[rhs].y
        } ?? 0
        let rotated = Array(samples[start...]) + Array(samples[..<start])
        let simplified = simplify(rotated + [rotated[0]], tolerance: diagonal * 0.09)
        let cornerCount = max(simplified.count - 1, 0)
        let shape: TikZNodeShape
        if cornerCount == 3 {
            shape = .triangle
        } else if cornerCount >= 6 {
            shape = .ellipse
        } else {
            shape = .rectangle
        }
        return Result(shape: shape, bounds: bounds)
    }

    private func simplify(_ points: [CGPoint], tolerance: CGFloat) -> [CGPoint] {
        guard points.count > 2 else { return points }
        let first = points[0]
        let last = points[points.count - 1]
        var farthest = CGFloat.zero
        var farthestIndex = 0
        for index in 1..<(points.count - 1) {
            let distance = distanceToSegment(points[index], first, last)
            if distance > farthest {
                farthest = distance
                farthestIndex = index
            }
        }
        guard farthest > tolerance else { return [first, last] }
        let left = simplify(Array(points[...farthestIndex]), tolerance: tolerance)
        let right = simplify(Array(points[farthestIndex...]), tolerance: tolerance)
        return Array(left.dropLast()) + right
    }

    private func distanceToSegment(
        _ point: CGPoint, _ start: CGPoint, _ end: CGPoint
    ) -> CGFloat {
        let dx = end.x - start.x
        let dy = end.y - start.y
        let lengthSquared = dx * dx + dy * dy
        guard lengthSquared > 0 else {
            return hypot(point.x - start.x, point.y - start.y)
        }
        let fraction = min(max(
            ((point.x - start.x) * dx + (point.y - start.y) * dy) / lengthSquared,
            0
        ), 1)
        return hypot(point.x - start.x - fraction * dx,
                     point.y - start.y - fraction * dy)
    }
}
