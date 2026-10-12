// Direct TikZ canvas using one deterministic interaction layer for taps, menus, shapes, and connectors.

import SwiftUI

struct TikZCanvasView: View {
    static let coordinateSpaceName = "ndTikZCanvas"

    let graph: TikZGraph
    let previewImage: UIImage?
    let logicalCanvasSize: CGSize
    let activeTool: TikZCanvasTool
    let preferredConnectorTool: TikZCanvasTool
    let connectionPointCounts: [String: Int]
    let draftNodeStyle: TikZNodeStyle
    let draftEdgeStyle: TikZEdgeStyle
    let selectedNodeName: String?
    let selectedEdgeID: String?
    let editingNodeName: String?
    let editingEdgeID: String?
    @Binding var labelDraft: String

    let onNodeSingleTap: (TikZNode) -> Void
    let onNodeDoubleTap: (TikZNode) -> Void
    let onEdgeSingleTap: (TikZEdge) -> Void
    let onEdgeDoubleTap: (TikZEdge) -> Void
    let onClearSelection: () -> Void

    let onNodeMove: (TikZNode, CGPoint) -> Void
    let onNodeResize: (TikZNode, CGPoint, CGSize) -> Void
    let onNodeDelete: (TikZNode) -> Void
    let onNodeDuplicate: (TikZNode) -> Void
    let onNodeBringToFront: (TikZNode) -> Void
    let onNodeSendToBack: (TikZNode) -> Void
    let onNodeAddConnectionPoint: (TikZNode) -> Void

    let onEdgeDelete: (TikZEdge) -> Void
    let onEdgeBringToFront: (TikZEdge) -> Void
    let onEdgeSendToBack: (TikZEdge) -> Void
    let onEdgeCurveControlMove: (TikZEdge, Int, CGPoint) -> Void
    let onEdgeBendMove: (TikZEdge, Int, CGPoint) -> Void
    let onEdgeBendRemove: (TikZEdge, Int) -> Void
    let onEdgeAddBendPoint: (TikZEdge, Int, CGPoint) -> Void

    let onLabelCommit: () -> Void
    let onConnectorAutoActivated: () -> Void
    let onConnectorDrop: (TikZNode, TikZNode?, CGPoint) -> Void
    let onShapeCreate: (TikZNodeShape, CGPoint, CGSize) -> Void

    @State private var shapeDragStart: CGPoint?
    @State private var shapeDragCurrent: CGPoint?
    @State private var connectorSourceName: String?
    @State private var connectorCurrentPoint: CGPoint?

    private let mapper = TikZCoordinateMapper()

    var body: some View {
        GeometryReader { proxy in
            let canvas = fittedCanvas(in: proxy.size)

            ZStack {
                Color(uiColor: .secondarySystemBackground)

                ZStack {
                    Color.white

                    if graph.nodes.isEmpty && graph.edges.isEmpty, let previewImage {
                        Image(uiImage: previewImage)
                            .resizable()
                            .scaledToFit()
                            .allowsHitTesting(false)
                    }

                    TikZCanvasInteractionOverlay(
                        graph: graph,
                        canvasSize: canvas,
                        activeTool: activeTool,
                        preferredConnectorTool: preferredConnectorTool,
                        connectionPointCounts: connectionPointCounts,
                        onNodeSingleTap: { name in
                            if let node = node(named: name) {
                                onNodeSingleTap(node)
                            }
                        },
                        onNodeDoubleTap: { name in
                            if let node = node(named: name) {
                                onNodeDoubleTap(node)
                            }
                        },
                        onEdgeSingleTap: { id in
                            if let edge = edge(id: id) {
                                onEdgeSingleTap(edge)
                            }
                        },
                        onEdgeDoubleTap: { id in
                            if let edge = edge(id: id) {
                                onEdgeDoubleTap(edge)
                            }
                        },
                        onClearSelection: onClearSelection,
                        onConnectorAutoActivated: onConnectorAutoActivated,
                        onConnectorDragChanged: { sourceName, point in
                            connectorSourceName = sourceName
                            connectorCurrentPoint = point
                        },
                        onConnectorDragEnded: { sourceName, targetName, point in
                            defer {
                                connectorSourceName = nil
                                connectorCurrentPoint = nil
                            }
                            guard let source = node(named: sourceName) else {
                                return
                            }
                            let target = targetName.flatMap { node(named: $0) }
                            onConnectorDrop(
                                source,
                                target,
                                mapper.tikzPoint(for: point, in: canvas)
                            )
                        },
                        onShapeDragChanged: { start, current in
                            shapeDragStart = start
                            shapeDragCurrent = current
                        },
                        onShapeDragEnded: { shape, start, end in
                            defer {
                                shapeDragStart = nil
                                shapeDragCurrent = nil
                            }
                            guard
                                abs(end.x - start.x) >= 10,
                                abs(end.y - start.y) >= 10
                            else {
                                return
                            }

                            let first = mapper.tikzPoint(for: start, in: canvas)
                            let second = mapper.tikzPoint(for: end, in: canvas)
                            let center = CGPoint(
                                x: (first.x + second.x) / 2,
                                y: (first.y + second.y) / 2
                            )
                            let size = CGSize(
                                width: abs(first.x - second.x),
                                height: abs(first.y - second.y)
                            )
                            onShapeCreate(shape, center, size)
                        },
                        onNodeEditLabel: { name in
                            if let node = node(named: name) {
                                onNodeDoubleTap(node)
                            }
                        },
                        onNodeDuplicate: { name in
                            if let node = node(named: name) {
                                onNodeDuplicate(node)
                            }
                        },
                        onNodeBringToFront: { name in
                            if let node = node(named: name) {
                                onNodeBringToFront(node)
                            }
                        },
                        onNodeSendToBack: { name in
                            if let node = node(named: name) {
                                onNodeSendToBack(node)
                            }
                        },
                        onNodeAddConnectionPoint: { name in
                            if let node = node(named: name) {
                                onNodeAddConnectionPoint(node)
                            }
                        },
                        onNodeDelete: { name in
                            if let node = node(named: name) {
                                onNodeDelete(node)
                            }
                        },
                        onEdgeEditLabel: { id in
                            if let edge = edge(id: id) {
                                onEdgeDoubleTap(edge)
                            }
                        },
                        onEdgeAddBendPoint: { id, point in
                            guard
                                let edge = edge(id: id),
                                let sourceNode = node(named: edge.source),
                                let targetNode = node(named: edge.target)
                            else {
                                return
                            }
                            let segmentIndex = TikZEdgePathGeometry()
                                .nearestSegmentIndex(
                                    to: point,
                                    edge: edge,
                                    sourceNode: sourceNode,
                                    targetNode: targetNode,
                                    in: canvas
                                )
                            onEdgeAddBendPoint(
                                edge,
                                segmentIndex,
                                mapper.tikzPoint(for: point, in: canvas)
                            )
                        },
                        onEdgeBringToFront: { id in
                            if let edge = edge(id: id) {
                                onEdgeBringToFront(edge)
                            }
                        },
                        onEdgeSendToBack: { id in
                            if let edge = edge(id: id) {
                                onEdgeSendToBack(edge)
                            }
                        },
                        onEdgeDelete: { id in
                            if let edge = edge(id: id) {
                                onEdgeDelete(edge)
                            }
                        }
                    )

                    ForEach(graph.edges) { edge in
                        if
                            let sourceNode = node(named: edge.source),
                            let targetNode = node(named: edge.target)
                        {
                            TikZEdgeView(
                                edge: edge,
                                sourceNode: sourceNode,
                                targetNode: targetNode,
                                canvasSize: canvas,
                                selected: selectedEdgeID == edge.id,
                                editingLabel: editingEdgeID == edge.id ? $labelDraft : nil,
                                onCommitLabel: onLabelCommit
                            )
                        }
                    }

                    ForEach(graph.nodes) { node in
                        TikZNodeView(
                            node: node,
                            canvasSize: canvas,
                            editingLabel: editingNodeName == node.name ? $labelDraft : nil,
                            onCommitLabel: onLabelCommit
                        )
                    }

                    ForEach(graph.nodes) { node in
                        TikZConnectionPointOverlay(
                            node: node,
                            count: connectionPointCounts[node.name]
                                ?? TikZConnectionPointMetadata.defaultCount,
                            canvasSize: canvas
                        )
                        .opacity(
                            activeTool.connectorKind != nil
                            || selectedNodeName == node.name
                            || connectorSourceName != nil
                                ? 1.0
                                : 0.38
                        )
                    }

                    if activeTool == .select, let selectedNode {
                        TikZNodeSelectionOverlay(
                            node: selectedNode,
                            canvasSize: canvas,
                            onMove: {
                                onNodeMove(selectedNode, $0)
                            },
                            onResize: { center, size in
                                onNodeResize(selectedNode, center, size)
                            }
                        )
                    }

                    if
                        activeTool == .select,
                        let selectedEdge,
                        let sourceNode = node(named: selectedEdge.source),
                        let targetNode = node(named: selectedEdge.target)
                    {
                        TikZEdgeSelectionOverlay(
                            edge: selectedEdge,
                            sourceNode: sourceNode,
                            targetNode: targetNode,
                            canvasSize: canvas,
                            onCurveControlMove: { index, point in
                                onEdgeCurveControlMove(selectedEdge, index, point)
                            },
                            onBendMove: { index, point in
                                onEdgeBendMove(selectedEdge, index, point)
                            },
                            onBendRemove: { index in
                                onEdgeBendRemove(selectedEdge, index)
                            }
                        )
                    }

                    if let connectorSource, let connectorCurrentPoint {
                        TikZConnectorPreviewView(
                            sourceNode: connectorSource,
                            currentPoint: connectorCurrentPoint,
                            canvasSize: canvas,
                            style: draftEdgeStyle,
                            kind: activeTool.connectorKind
                                ?? preferredConnectorTool.connectorKind
                                ?? .straight
                        )
                    }

                    if let previewRect = draftViewRect {
                        draftShape(in: previewRect)
                    }
                }
                .frame(width: canvas.width, height: canvas.height)
                .coordinateSpace(name: Self.coordinateSpaceName)
                .clipped()
                .shadow(radius: 4, y: 2)
            }
        }
    }

    private var selectedNode: TikZNode? {
        guard let selectedNodeName else { return nil }
        return node(named: selectedNodeName)
    }

    private var selectedEdge: TikZEdge? {
        guard let selectedEdgeID else { return nil }
        return edge(id: selectedEdgeID)
    }

    private var connectorSource: TikZNode? {
        guard let connectorSourceName else { return nil }
        return node(named: connectorSourceName)
    }

    private func node(named name: String) -> TikZNode? {
        graph.nodes.first { $0.name == name }
    }

    private func edge(id: String) -> TikZEdge? {
        graph.edges.first { $0.id == id }
    }

    @ViewBuilder
    private func draftShape(in rect: CGRect) -> some View {
        if activeTool == .triangle {
            TikZTriangleShape()
                .fill(draftNodeStyle.fillColor.color.opacity(0.75))
                .overlay(
                    TikZTriangleShape().stroke(
                        draftNodeStyle.strokeColor.color,
                        lineWidth: max(CGFloat(draftNodeStyle.lineWidth), 0.8)
                    )
                )
                .frame(width: rect.width, height: rect.height)
                .position(x: rect.midX, y: rect.midY)
        } else if activeTool == .circle {
            Circle()
                .fill(draftNodeStyle.fillColor.color.opacity(0.75))
                .overlay(Circle().stroke(
                    draftNodeStyle.strokeColor.color,
                    lineWidth: max(CGFloat(draftNodeStyle.lineWidth), 0.8)
                ))
                .frame(width: rect.width, height: rect.height)
                .position(x: rect.midX, y: rect.midY)
        } else if activeTool == .ellipse {
            Ellipse()
                .fill(draftNodeStyle.fillColor.color.opacity(0.75))
                .overlay(
                    Ellipse().stroke(
                        draftNodeStyle.strokeColor.color,
                        lineWidth: max(CGFloat(draftNodeStyle.lineWidth), 0.8)
                    )
                )
                .frame(width: rect.width, height: rect.height)
                .position(x: rect.midX, y: rect.midY)
        } else {
            Rectangle()
                .fill(draftNodeStyle.fillColor.color.opacity(0.75))
                .overlay(
                    Rectangle().stroke(
                        draftNodeStyle.strokeColor.color,
                        lineWidth: max(CGFloat(draftNodeStyle.lineWidth), 0.8)
                    )
                )
                .frame(width: rect.width, height: rect.height)
                .position(x: rect.midX, y: rect.midY)
        }
    }

    private var draftViewRect: CGRect? {
        guard let start = shapeDragStart, let current = shapeDragCurrent else {
            return nil
        }
        return CGRect(
            x: min(start.x, current.x),
            y: min(start.y, current.y),
            width: abs(current.x - start.x),
            height: abs(current.y - start.y)
        )
    }

    private func fittedCanvas(in available: CGSize) -> CGSize {
        let logicalWidth = max(logicalCanvasSize.width, 64)
        let logicalHeight = max(logicalCanvasSize.height, 64)
        let aspect = logicalWidth / logicalHeight
        let widthFromHeight = available.height * aspect

        if widthFromHeight <= available.width {
            return CGSize(width: widthFromHeight, height: available.height)
        }
        return CGSize(
            width: available.width,
            height: available.width / aspect
        )
    }
}
