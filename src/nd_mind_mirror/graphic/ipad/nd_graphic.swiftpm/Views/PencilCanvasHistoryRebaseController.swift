import PencilKit
import UIKit

/// Owns creation of PencilKit canvas surfaces and replaces the surface after an app-history restore.
/// The outer scroll view and viewport remain intact; only PencilKit's internal drawing surface is renewed.
@MainActor
final class PencilCanvasHistoryRebaseController {
    func makeCanvas(
        frame: CGRect,
        drawing: PKDrawing,
        delegate: PKCanvasViewDelegate
    ) -> PKCanvasView {
        let canvas = PKCanvasView(frame: frame)
        canvas.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        canvas.backgroundColor = .clear
        canvas.isOpaque = false
        canvas.drawingPolicy = .pencilOnly
        canvas.isScrollEnabled = false
        canvas.bounces = false
        canvas.contentInset = .zero
        canvas.contentOffset = .zero
        canvas.contentSize = frame.size
        canvas.minimumZoomScale = 1.0
        canvas.maximumZoomScale = 1.0
        canvas.zoomScale = 1.0

        // Application history is authoritative. PencilKit must not keep an independent
        // undo stack that can replay strokes after the application has already undone them.
        canvas.undoManager?.removeAllActions()
        canvas.undoManager?.disableUndoRegistration()

        // Load the authoritative drawing before installing the delegate so construction
        // cannot be mistaken for a user edit.
        canvas.drawing = drawing
        canvas.delegate = delegate
        return canvas
    }

    func replaceCanvas(
        _ currentCanvas: PKCanvasView,
        in contentView: UIView,
        below upperView: UIView?,
        drawing: PKDrawing,
        delegate: PKCanvasViewDelegate
    ) -> PKCanvasView {
        let replacement = makeCanvas(
            frame: currentCanvas.frame,
            drawing: drawing,
            delegate: delegate
        )

        if let upperView, upperView.superview === contentView {
            contentView.insertSubview(replacement, belowSubview: upperView)
        } else if let index = contentView.subviews.firstIndex(of: currentCanvas) {
            contentView.insertSubview(replacement, at: index)
        } else {
            contentView.addSubview(replacement)
        }

        currentCanvas.delegate = nil
        currentCanvas.removeFromSuperview()
        return replacement
    }
}
