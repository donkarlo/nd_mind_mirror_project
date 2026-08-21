import PencilKit
import SwiftUI
import UIKit

/// Pencil canvas inside a UIScrollView. Pencil draws; fingers pan and pinch.
/// Remote save acknowledgements never reset the live viewport.
struct PencilCanvasView: UIViewRepresentable {
    let drawing: PKDrawing
    let backgroundImage: UIImage?
    let documentToken: Int
    let documentIdentifier: String
    let tool: GraphicTool
    let color: Color
    let width: Double
    let logicalCanvasSize: CGSize
    let onDrawingChanged: (PKDrawing) -> Void
    let onUndoManagerChanged: (UndoManager?) -> Void

    func makeCoordinator() -> Coordinator {
        Coordinator(onDrawingChanged: onDrawingChanged, onUndoManagerChanged: onUndoManagerChanged)
    }

    func makeUIView(context: Context) -> UIScrollView {
        let scroll = UIScrollView()
        scroll.backgroundColor = UIColor.secondarySystemBackground
        scroll.delegate = context.coordinator
        scroll.bounces = true
        scroll.bouncesZoom = true
        scroll.alwaysBounceHorizontal = true
        scroll.alwaysBounceVertical = true
        scroll.showsHorizontalScrollIndicator = true
        scroll.showsVerticalScrollIndicator = true
        scroll.contentInsetAdjustmentBehavior = .never
        scroll.panGestureRecognizer.allowedTouchTypes = [NSNumber(value: UITouch.TouchType.direct.rawValue)]
        scroll.pinchGestureRecognizer?.allowedTouchTypes = [NSNumber(value: UITouch.TouchType.direct.rawValue)]

        let content = UIView(frame: CGRect(origin: .zero, size: logicalCanvasSize))
        content.backgroundColor = .white

        let background = UIImageView(frame: content.bounds)
        background.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        background.contentMode = .scaleAspectFit
        background.backgroundColor = .white
        background.image = backgroundImage
        content.addSubview(background)

        let canvas = PKCanvasView(frame: content.bounds)
        canvas.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        canvas.backgroundColor = .clear
        canvas.isOpaque = false
        canvas.drawingPolicy = .pencilOnly
        canvas.isScrollEnabled = false
        canvas.bounces = false
        canvas.delegate = context.coordinator
        canvas.drawing = drawing
        content.addSubview(canvas)

        scroll.addSubview(content)
        scroll.contentSize = logicalCanvasSize

        context.coordinator.scrollView = scroll
        context.coordinator.contentView = content
        context.coordinator.backgroundView = background
        context.coordinator.canvas = canvas
        context.coordinator.documentToken = documentToken
        context.coordinator.documentIdentifier = documentIdentifier
        context.coordinator.logicalCanvasSize = logicalCanvasSize
        applyTool(canvas)

        DispatchQueue.main.async {
            context.coordinator.fitCanvas(reset: true)
            context.coordinator.onUndoManagerChanged(canvas.undoManager)
        }
        return scroll
    }

    func updateUIView(_ scroll: UIScrollView, context: Context) {
        let coordinator = context.coordinator
        coordinator.onDrawingChanged = onDrawingChanged
        coordinator.onUndoManagerChanged = onUndoManagerChanged
        coordinator.backgroundView?.image = backgroundImage

        let sizeChanged = coordinator.logicalCanvasSize != logicalCanvasSize
        let documentChanged = coordinator.documentIdentifier != documentIdentifier

        if sizeChanged {
            coordinator.logicalCanvasSize = logicalCanvasSize
            coordinator.contentView?.frame = CGRect(origin: .zero, size: logicalCanvasSize)
            coordinator.backgroundView?.frame = CGRect(origin: .zero, size: logicalCanvasSize)
            coordinator.canvas?.frame = CGRect(origin: .zero, size: logicalCanvasSize)
            scroll.contentSize = logicalCanvasSize
        }

        if coordinator.documentToken != documentToken {
            coordinator.documentToken = documentToken
            coordinator.documentIdentifier = documentIdentifier
            coordinator.loading = true
            coordinator.canvas?.drawing = drawing
            coordinator.loading = false
            // A new file gets a clean fit. An update of the same file keeps
            // the exact zoom and pan the user was using while writing.
            if documentChanged || sizeChanged {
                DispatchQueue.main.async { coordinator.fitCanvas(reset: true) }
            } else {
                DispatchQueue.main.async { coordinator.centerCanvas() }
            }
        } else if sizeChanged {
            DispatchQueue.main.async { coordinator.fitCanvas(reset: true) }
        }

        if let canvas = coordinator.canvas { applyTool(canvas) }
    }

    private func applyTool(_ canvas: PKCanvasView) {
        switch tool {
        case .pencil:
            canvas.tool = PKInkingTool(.pencil, color: UIColor(color), width: CGFloat(max(1.0, width)))
        case .highlighter:
            canvas.tool = PKInkingTool(
                .marker,
                color: UIColor(color).withAlphaComponent(0.34),
                width: CGFloat(max(10.0, width * 2.6))
            )
        case .eraser:
            canvas.tool = PKEraserTool(.vector)
        }
    }

    final class Coordinator: NSObject, PKCanvasViewDelegate, UIScrollViewDelegate {
        weak var scrollView: UIScrollView?
        weak var canvas: PKCanvasView?
        weak var contentView: UIView?
        weak var backgroundView: UIImageView?
        var documentToken = -1
        var documentIdentifier = ""
        var logicalCanvasSize = CGSize(width: 1600, height: 1000)
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

        func viewForZooming(in scrollView: UIScrollView) -> UIView? { contentView }
        func scrollViewDidZoom(_ scrollView: UIScrollView) { centerCanvas() }

        func fitCanvas(reset: Bool) {
            guard let scroll = scrollView,
                  scroll.bounds.width > 1,
                  scroll.bounds.height > 1,
                  logicalCanvasSize.width > 1,
                  logicalCanvasSize.height > 1 else { return }
            let fit = min(scroll.bounds.width / logicalCanvasSize.width, scroll.bounds.height / logicalCanvasSize.height)
            let safeFit = max(fit, 0.05)
            scroll.minimumZoomScale = max(safeFit * 0.5, 0.05)
            scroll.maximumZoomScale = max(safeFit * 10.0, 5.0)
            if reset {
                scroll.setZoomScale(safeFit, animated: false)
                scroll.contentOffset = .zero
            }
            centerCanvas()
        }

        func centerCanvas() {
            guard let scroll = scrollView else { return }
            let horizontal = max((scroll.bounds.width - scroll.contentSize.width) / 2, 0)
            let vertical = max((scroll.bounds.height - scroll.contentSize.height) / 2, 0)
            scroll.contentInset = UIEdgeInsets(top: vertical, left: horizontal, bottom: vertical, right: horizontal)
        }
    }
}
