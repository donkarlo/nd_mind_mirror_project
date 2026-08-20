import PencilKit
import SwiftUI

struct PencilCanvasView: UIViewRepresentable {
    let drawing: PKDrawing
    let documentToken: Int
    let tool: GraphicTool
    let color: Color
    let width: Double
    let logicalCanvasSize: CGSize
    let onDrawingChanged: (PKDrawing) -> Void
    let onUndoManagerChanged: (UndoManager?) -> Void

    func makeCoordinator() -> Coordinator {
        Coordinator(
            onDrawingChanged: onDrawingChanged,
            onUndoManagerChanged: onUndoManagerChanged
        )
    }

    func makeUIView(context: Context) -> PKCanvasView {
        let canvas = PKCanvasView(frame: CGRect(origin: .zero, size: logicalCanvasSize))
        canvas.backgroundColor = .white
        canvas.isOpaque = true
        canvas.drawingPolicy = .pencilOnly
        canvas.isScrollEnabled = false
        canvas.bounces = false
        canvas.delegate = context.coordinator
        context.coordinator.documentToken = documentToken
        context.coordinator.canvas = canvas
        context.coordinator.loading = true
        canvas.drawing = drawing
        context.coordinator.loading = false
        applyTool(canvas)
        DispatchQueue.main.async {
            context.coordinator.onUndoManagerChanged(canvas.undoManager)
        }
        return canvas
    }

    func updateUIView(_ canvas: PKCanvasView, context: Context) {
        context.coordinator.onDrawingChanged = onDrawingChanged
        context.coordinator.onUndoManagerChanged = onUndoManagerChanged
        if context.coordinator.documentToken != documentToken {
            context.coordinator.documentToken = documentToken
            context.coordinator.loading = true
            canvas.drawing = drawing
            context.coordinator.loading = false
        }
        applyTool(canvas)
    }

    private func applyTool(_ canvas: PKCanvasView) {
        switch tool {
        case .pencil:
            canvas.tool = PKInkingTool(
                .pencil,
                color: UIColor(color),
                width: CGFloat(max(1.0, width))
            )
        case .eraser:
            canvas.tool = PKEraserTool(.vector)
        }
    }

    final class Coordinator: NSObject, PKCanvasViewDelegate {
        weak var canvas: PKCanvasView?
        var documentToken = 0
        var loading = false
        var onDrawingChanged: (PKDrawing) -> Void
        var onUndoManagerChanged: (UndoManager?) -> Void

        init(
            onDrawingChanged: @escaping (PKDrawing) -> Void,
            onUndoManagerChanged: @escaping (UndoManager?) -> Void
        ) {
            self.onDrawingChanged = onDrawingChanged
            self.onUndoManagerChanged = onUndoManagerChanged
        }

        func canvasViewDrawingDidChange(_ canvasView: PKCanvasView) {
            guard !loading else { return }
            onDrawingChanged(canvasView.drawing)
            onUndoManagerChanged(canvasView.undoManager)
        }
    }
}
