// Geometry helpers shared by TikZ rendering, selection handles, and connectors.

import CoreGraphics

struct TikZNodeGeometry {
    private let mapper = TikZCoordinateMapper()

    func rect(for node: TikZNode, in canvasSize: CGSize) -> CGRect {
        let center = mapper.viewPoint(for: node.position, in: canvasSize)
        let size = mapper.viewSize(
            width: node.width,
            height: node.height,
            in: canvasSize
        )
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
            if node.shape == .rectangle {
                return rect.insetBy(dx: -tolerance, dy: -tolerance).contains(point)
            }

            let center = CGPoint(x: rect.midX, y: rect.midY)
            let rx = max(rect.width / 2 + tolerance, 1)
            let ry = max(rect.height / 2 + tolerance, 1)
            let nx = (point.x - center.x) / rx
            let ny = (point.y - center.y) / ry
            return nx * nx + ny * ny <= 1
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

        if node.shape == .ellipse {
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
