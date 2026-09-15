// UIKit-backed interaction surface for deterministic Pencil/touch behavior on the TikZ canvas.

import SwiftUI
import UIKit

struct TikZCanvasInteractionOverlay: UIViewRepresentable {
    let graph: TikZGraph
    let canvasSize: CGSize
    let activeTool: TikZCanvasTool

    let onNodeSingleTap: (String) -> Void
    let onNodeDoubleTap: (String) -> Void
    let onEdgeSingleTap: (String) -> Void
    let onEdgeDoubleTap: (String) -> Void
    let onClearSelection: () -> Void

    let onConnectorDragChanged: (String, CGPoint) -> Void
    let onConnectorDragEnded: (String, String?) -> Void
    let onShapeDragChanged: (CGPoint, CGPoint) -> Void
    let onShapeDragEnded: (TikZNodeShape, CGPoint, CGPoint) -> Void

    let onNodeEditLabel: (String) -> Void
    let onNodeDuplicate: (String) -> Void
    let onNodeBringToFront: (String) -> Void
    let onNodeSendToBack: (String) -> Void
    let onNodeDelete: (String) -> Void

    let onEdgeEditLabel: (String) -> Void
    let onEdgeAddBendPoint: (String, CGPoint) -> Void
    let onEdgeBringToFront: (String) -> Void
    let onEdgeSendToBack: (String) -> Void
    let onEdgeDelete: (String) -> Void

    func makeCoordinator() -> TikZCanvasInteractionCoordinator {
        TikZCanvasInteractionCoordinator()
    }

    func makeUIView(context: Context) -> UIView {
        let view = UIView(frame: .zero)
        view.backgroundColor = .clear
        view.isOpaque = false
        context.coordinator.attach(to: view)
        return view
    }

    func updateUIView(
        _ uiView: UIView,
        context: Context
    ) {
        context.coordinator.update(
            graph: graph,
            canvasSize: canvasSize,
            activeTool: activeTool,
            onNodeSingleTap: onNodeSingleTap,
            onNodeDoubleTap: onNodeDoubleTap,
            onEdgeSingleTap: onEdgeSingleTap,
            onEdgeDoubleTap: onEdgeDoubleTap,
            onClearSelection: onClearSelection,
            onConnectorDragChanged: onConnectorDragChanged,
            onConnectorDragEnded: onConnectorDragEnded,
            onShapeDragChanged: onShapeDragChanged,
            onShapeDragEnded: onShapeDragEnded,
            onNodeEditLabel: onNodeEditLabel,
            onNodeDuplicate: onNodeDuplicate,
            onNodeBringToFront: onNodeBringToFront,
            onNodeSendToBack: onNodeSendToBack,
            onNodeDelete: onNodeDelete,
            onEdgeEditLabel: onEdgeEditLabel,
            onEdgeAddBendPoint: onEdgeAddBendPoint,
            onEdgeBringToFront: onEdgeBringToFront,
            onEdgeSendToBack: onEdgeSendToBack,
            onEdgeDelete: onEdgeDelete
        )
    }
}
