import PencilKit
import SwiftUI

struct PencilCanvasView: UIViewRepresentable {
    let tool: DrawingTool
    let clearToken: Int
    let onStrokeFinished: ([CGPoint], CGSize) -> Void
    let onHandwritingFinished: ([PKStroke], CGSize) -> Void

    func makeCoordinator() -> Coordinator {
        Coordinator(
            tool: tool,
            onStrokeFinished: onStrokeFinished,
            onHandwritingFinished: onHandwritingFinished
        )
    }

    func makeUIView(context: Context) -> PKCanvasView {
        let canvas = PKCanvasView(frame: .zero)
        canvas.backgroundColor = .clear
        canvas.isOpaque = false
        canvas.delegate = context.coordinator
        canvas.drawingPolicy = .pencilOnly
        canvas.tool = PKInkingTool(.pen, color: .systemBlue, width: 3)
        canvas.isScrollEnabled = false
        context.coordinator.canvas = canvas
        context.coordinator.lastClearToken = clearToken
        return canvas
    }

    func updateUIView(_ canvas: PKCanvasView, context: Context) {
        context.coordinator.tool = tool
        context.coordinator.onStrokeFinished = onStrokeFinished
        context.coordinator.onHandwritingFinished = onHandwritingFinished
        if context.coordinator.lastClearToken != clearToken {
            context.coordinator.lastClearToken = clearToken
            context.coordinator.isProgrammaticClear = true
            canvas.drawing = PKDrawing()
            context.coordinator.processedStrokeCount = 0
            context.coordinator.isProgrammaticClear = false
        }
    }

    final class Coordinator: NSObject, PKCanvasViewDelegate {
        weak var canvas: PKCanvasView?
        var tool: DrawingTool
        var onStrokeFinished: ([CGPoint], CGSize) -> Void
        var onHandwritingFinished: ([PKStroke], CGSize) -> Void
        var processedStrokeCount = 0
        var debounceTask: Task<Void, Never>?
        var isProgrammaticClear = false
        var lastClearToken = 0

        init(
            tool: DrawingTool,
            onStrokeFinished: @escaping ([CGPoint], CGSize) -> Void,
            onHandwritingFinished: @escaping ([PKStroke], CGSize) -> Void
        ) {
            self.tool = tool
            self.onStrokeFinished = onStrokeFinished
            self.onHandwritingFinished = onHandwritingFinished
        }

        func canvasViewDrawingDidChange(_ canvasView: PKCanvasView) {
            guard !isProgrammaticClear else { return }
            debounceTask?.cancel()
            let delay: UInt64 = tool == .text ? 900_000_000 : 260_000_000
            debounceTask = Task { @MainActor [weak self, weak canvasView] in
                try? await Task.sleep(nanoseconds: delay)
                guard !Task.isCancelled,
                      let self,
                      let canvasView else { return }
                let strokes = canvasView.drawing.strokes
                guard strokes.count > self.processedStrokeCount else { return }
                let newStrokes = Array(strokes[self.processedStrokeCount..<strokes.count])
                self.processedStrokeCount = strokes.count

                if self.tool == .text {
                    self.onHandwritingFinished(newStrokes, canvasView.bounds.size)
                    return
                }

                for stroke in newStrokes {
                    let points = stroke.path.map { $0.location }
                    if points.count >= 2 {
                        self.onStrokeFinished(points, canvasView.bounds.size)
                    }
                }
            }
        }
    }
}
