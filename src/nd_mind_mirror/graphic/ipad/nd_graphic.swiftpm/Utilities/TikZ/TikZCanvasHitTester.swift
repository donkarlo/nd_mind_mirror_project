// Deterministic node/edge hit testing shared by taps, long-press menus, and Pencil connectors.

import CoreGraphics

struct TikZCanvasHitTester {
    private let geometry = TikZNodeGeometry()

    func target(
        at point: CGPoint,
        in graph: TikZGraph,
        canvasSize: CGSize
    ) -> TikZCanvasHitTarget? {
        if let node = node(at: point, in: graph, canvasSize: canvasSize, tolerance: 12) {
            return .node(node.name)
        }
        if let edge = edge(at: point, in: graph, canvasSize: canvasSize, tolerance: 18) {
            return .edge(edge.id)
        }
        return nil
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
            return contains(point, node: node, canvasSize: canvasSize, tolerance: tolerance)
        }
    }

    func edge(
        at point: CGPoint,
        in graph: TikZGraph,
        canvasSize: CGSize,
        tolerance: CGFloat = 18
    ) -> TikZEdge? {
        graph.edges.reversed().first { edge in
            guard
                let sourceNode = graph.nodes.first(where: { $0.name == edge.source }),
                let targetNode = graph.nodes.first(where: { $0.name == edge.target })
            else { return false }

            let endpoints = geometry.connectorEndpoints(
                from: sourceNode,
                to: targetNode,
                in: canvasSize
            )
            let effectiveTolerance = max(tolerance, CGFloat(edge.lineWidth) / 2 + 10)
            return distance(
                from: point,
                toSegmentFrom: endpoints.start,
                to: endpoints.end
            ) <= effectiveTolerance
        }
    }

    private func contains(
        _ point: CGPoint,
        node: TikZNode,
        canvasSize: CGSize,
        tolerance: CGFloat
    ) -> Bool {
        let rect = geometry.rect(for: node, in: canvasSize)
        if node.shape == .rectangle {
            return rect.insetBy(dx: -tolerance, dy: -tolerance).contains(point)
        }

        let center = CGPoint(x: rect.midX, y: rect.midY)
        let radiusX = max(rect.width / 2 + tolerance, 1)
        let radiusY = max(rect.height / 2 + tolerance, 1)
        let normalizedX = (point.x - center.x) / radiusX
        let normalizedY = (point.y - center.y) / radiusY
        return normalizedX * normalizedX + normalizedY * normalizedY <= 1
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
            return hypot(point.x - start.x, point.y - start.y)
        }

        let projection = (
            (point.x - start.x) * dx
            + (point.y - start.y) * dy
        ) / lengthSquared
        let t = min(max(projection, 0), 1)
        let closest = CGPoint(
            x: start.x + t * dx,
            y: start.y + t * dy
        )
        return hypot(point.x - closest.x, point.y - closest.y)
    }
}
