// Deterministic node/edge hit testing shared by taps, menus, and Pencil connectors.

import CoreGraphics

struct TikZCanvasHitTester {
    private let nodeGeometry = TikZNodeGeometry()
    private let edgeGeometry = TikZEdgePathGeometry()

    func target(
        at point: CGPoint,
        in graph: TikZGraph,
        canvasSize: CGSize
    ) -> TikZCanvasHitTarget? {
        if let node = node(
            at: point,
            in: graph,
            canvasSize: canvasSize,
            tolerance: 12
        ) {
            return .node(
                node.name
            )
        }

        if let edge = edge(
            at: point,
            in: graph,
            canvasSize: canvasSize,
            tolerance: 18
        ) {
            return .edge(
                edge.id
            )
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
        graph.nodes
            .reversed()
            .first {
                node in
                guard
                    node.name
                    != excludedName
                else {
                    return false
                }
                return contains(
                    point,
                    node: node,
                    canvasSize:
                        canvasSize,
                    tolerance:
                        tolerance
                )
            }
    }

    func edge(
        at point: CGPoint,
        in graph: TikZGraph,
        canvasSize: CGSize,
        tolerance: CGFloat = 18
    ) -> TikZEdge? {
        graph.edges
            .reversed()
            .first {
                edge in
                guard
                    let sourceNode =
                        graph.nodes
                        .first(
                            where: {
                                $0.name
                                    == edge.source
                            }
                        ),
                    let targetNode =
                        graph.nodes
                        .first(
                            where: {
                                $0.name
                                    == edge.target
                            }
                        )
                else {
                    return false
                }

                let effectiveTolerance =
                    max(
                        tolerance,
                        CGFloat(
                            edge.lineWidth
                        ) / 2 + 10
                    )

                return edgeGeometry
                    .distance(
                        from: point,
                        to: edge,
                        sourceNode:
                            sourceNode,
                        targetNode:
                            targetNode,
                        in: canvasSize
                    )
                    <= effectiveTolerance
            }
    }

    private func contains(
        _ point: CGPoint,
        node: TikZNode,
        canvasSize: CGSize,
        tolerance: CGFloat
    ) -> Bool {
        let rect = nodeGeometry
            .rect(
                for: node,
                in: canvasSize
            )

        return nodeGeometry.contains(
            point,
            in: rect,
            shape: node.shape,
            tolerance: tolerance
        )
    }
}
