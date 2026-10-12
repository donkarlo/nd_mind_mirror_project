// Geometry helpers shared by TikZ rendering, selection handles, and connectors.

import CoreGraphics

struct TikZNodeGeometry {
    private let mapper = TikZCoordinateMapper()

    func rect(for node: TikZNode, in canvasSize: CGSize) -> CGRect {
        let center = mapper.viewPoint(for: node.position, in: canvasSize)
        var size = mapper.viewSize(
            width: node.width,
            height: node.height,
            in: canvasSize
        )
        if node.shape == .circle {
            let diameter = min(size.width, size.height)
            size = CGSize(width: diameter, height: diameter)
        }
        return CGRect(
            x: center.x - size.width / 2,
            y: center.y - size.height / 2,
            width: size.width,
            height: size.height
        )
    }

    func node(
        at point: CGPoint,
        in graph: TikZGraph,
        canvasSize: CGSize,
        excluding excludedName: String? = nil,
        tolerance: CGFloat = 12
    ) -> TikZNode? {
        graph.nodes.reversed().first { node in
            guard node.name != excludedName else { return false }
            let rect = rect(for: node, in: canvasSize)
            return contains(point, in: rect, shape: node.shape, tolerance: tolerance)
        }
    }

    func contains(
        _ point: CGPoint,
        in rect: CGRect,
        shape: TikZNodeShape,
        tolerance: CGFloat = 0
    ) -> Bool {
        switch shape {
        case .rectangle:
            return rect.insetBy(dx: -tolerance, dy: -tolerance).contains(point)
        case .ellipse, .circle:
            let radiusX = max(rect.width / 2 + tolerance, 1)
            let radiusY = max(rect.height / 2 + tolerance, 1)
            let dx = (point.x - rect.midX) / radiusX
            let dy = (point.y - rect.midY) / radiusY
            return dx * dx + dy * dy <= 1
        case .triangle:
            let bounds = rect.insetBy(dx: -tolerance, dy: -tolerance)
            guard bounds.contains(point) else { return false }
            let progress = max(
                (point.y - bounds.minY) / max(bounds.height, 1), 0
            )
            let halfWidth = progress * bounds.width / 2
            return abs(point.x - bounds.midX) <= halfWidth
        }
    }

    func connectorEndpoints(
        from sourceNode: TikZNode,
        to targetNode: TikZNode,
        in canvasSize: CGSize
    ) -> (start: CGPoint, end: CGPoint) {
        let sourceCenter = mapper.viewPoint(for: sourceNode.position, in: canvasSize)
        let targetCenter = mapper.viewPoint(for: targetNode.position, in: canvasSize)
        return (
            boundaryPoint(for: sourceNode, toward: targetCenter, in: canvasSize),
            boundaryPoint(for: targetNode, toward: sourceCenter, in: canvasSize)
        )
    }

    func boundaryPoint(
        for node: TikZNode,
        toward target: CGPoint,
        in canvasSize: CGSize
    ) -> CGPoint {
        let nodeRect = rect(for: node, in: canvasSize)
        let center = CGPoint(x: nodeRect.midX, y: nodeRect.midY)
        let dx = target.x - center.x
        let dy = target.y - center.y

        guard abs(dx) > 0.001 || abs(dy) > 0.001 else {
            return center
        }

        if node.shape == .triangle {
            let top = CGPoint(x: nodeRect.midX, y: nodeRect.minY)
            let right = CGPoint(x: nodeRect.maxX, y: nodeRect.maxY)
            let left = CGPoint(x: nodeRect.minX, y: nodeRect.maxY)
            let vertices = [top, right, left]
            var nearest: (CGFloat, CGPoint)?
            for index in vertices.indices {
                let a = vertices[index]
                let b = vertices[(index + 1) % vertices.count]
                let sx = b.x - a.x
                let sy = b.y - a.y
                let denominator = dx * sy - dy * sx
                guard abs(denominator) > 0.00001 else { continue }
                let ox = a.x - center.x
                let oy = a.y - center.y
                let t = (ox * sy - oy * sx) / denominator
                let u = (ox * dy - oy * dx) / denominator
                if t > 0, u >= 0, u <= 1, nearest == nil || t < nearest!.0 {
                    nearest = (t, CGPoint(
                        x: center.x + t * dx,
                        y: center.y + t * dy
                    ))
                }
            }
            return nearest?.1 ?? center
        }

        if node.shape == .ellipse || node.shape == .circle {
            let rx = max(nodeRect.width / 2, 1)
            let ry = max(nodeRect.height / 2, 1)
            let denominator = sqrt(
                (dx * dx) / (rx * rx)
                + (dy * dy) / (ry * ry)
            )
            let scale = denominator > 0 ? 1 / denominator : 0
            return CGPoint(
                x: center.x + dx * scale,
                y: center.y + dy * scale
            )
        }

        let halfWidth = max(nodeRect.width / 2, 1)
        let halfHeight = max(nodeRect.height / 2, 1)
        let horizontalScale = abs(dx) > 0.001
            ? halfWidth / abs(dx)
            : .greatestFiniteMagnitude
        let verticalScale = abs(dy) > 0.001
            ? halfHeight / abs(dy)
            : .greatestFiniteMagnitude
        let scale = min(horizontalScale, verticalScale)

        return CGPoint(
            x: center.x + dx * scale,
            y: center.y + dy * scale
        )
    }
}
