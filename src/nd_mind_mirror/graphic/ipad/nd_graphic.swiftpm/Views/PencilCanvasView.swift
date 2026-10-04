// Hosts the PencilKit canvas, explicit zoom, image objects, and one unified lasso selection pipeline.

import PencilKit
import SwiftUI
import UIKit

/// Pencil canvas inside a UIScrollView where Pencil draws/selects while fingers navigate.
struct PencilCanvasView: UIViewRepresentable {
    let drawing: PKDrawing
    let backgroundImage: UIImage?
    let activeToolController: ActiveDrawingToolController
    let documentToken: Int
    let documentIdentifier: String
    let tool: GraphicTool
    let imageObjects: [CanvasImageObject]
    let selectedImageObjectID: UUID?
    let logicalCanvasSize: CGSize
    let showMeasurementGrid: Bool
    let showMeasurementRulers: Bool
    let zoom100RequestToken: Int
    let quickToolPalettePresented: Bool
    let onPencilContactBegan: (CGPoint) -> Void
    let onPencilSingleTap: (CGPoint) -> Void
    let onPencilDoubleTap: (CGPoint) -> Void
    let onDrawingChanged: (PKDrawing) -> Void
    let onUndoManagerChanged: (UndoManager?) -> Void
    let onZoomChanged: (CGFloat) -> Void
    let onImageObjectSelectionChanged: (UUID?) -> Void
    let onImageObjectsCommitted: ([CanvasImageObject], UUID?, String) -> Void

    func makeCoordinator() -> Coordinator {
        Coordinator(
            onDrawingChanged: onDrawingChanged,
            onUndoManagerChanged: onUndoManagerChanged,
            onZoomChanged: onZoomChanged
        )
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
        scroll.panGestureRecognizer.allowedTouchTypes = [
            NSNumber(value: UITouch.TouchType.direct.rawValue)
        ]
        scroll.panGestureRecognizer.minimumNumberOfTouches = 2
        scroll.panGestureRecognizer.maximumNumberOfTouches = 2
        scroll.pinchGestureRecognizer?.allowedTouchTypes = [
            NSNumber(value: UITouch.TouchType.direct.rawValue)
        ]
        scroll.minimumZoomScale = 0.05
        scroll.maximumZoomScale = 10.0

        let content = UIView(frame: CGRect(origin: .zero, size: logicalCanvasSize))
        content.backgroundColor = .white

        let background = UIImageView(frame: content.bounds)
        background.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        background.contentMode = .topLeft
        background.clipsToBounds = true
        background.backgroundColor = .white
        background.image = backgroundImage
        content.addSubview(background)

        let imageObjectLayer = CanvasImageObjectLayerView(frame: content.bounds)
        imageObjectLayer.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        imageObjectLayer.setObjects(imageObjects)
        content.addSubview(imageObjectLayer)

        let measurementGrid = MeasurementGridView(frame: content.bounds)
        measurementGrid.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        measurementGrid.showGrid = showMeasurementGrid
        measurementGrid.showRulers = showMeasurementRulers
        measurementGrid.isHidden = !showMeasurementGrid && !showMeasurementRulers
        content.addSubview(measurementGrid)

        let canvas = context.coordinator.historyRebaseController.makeCanvas(
            frame: content.bounds,
            drawing: drawing,
            delegate: context.coordinator
        )
        content.addSubview(canvas)

        let imageObjectInteraction = CanvasImageObjectInteractionView(frame: content.bounds)
        imageObjectInteraction.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        imageObjectInteraction.onSelectionChanged = { id in
            context.coordinator.onImageObjectSelectionChanged(id)
        }
        imageObjectInteraction.onPreviewObjectsChanged = { objects in
            imageObjectLayer.setObjects(objects)
        }
        imageObjectInteraction.onCommit = { objects, selectedID, actionName in
            context.coordinator.onImageObjectsCommitted(objects, selectedID, actionName)
        }
        imageObjectInteraction.setState(
            objects: imageObjects,
            selectedID: selectedImageObjectID,
            selectionEnabled: tool == .lasso,
            zoomScale: 1.0
        )
        content.addSubview(imageObjectInteraction)

        scroll.addSubview(content)
        scroll.contentSize = logicalCanvasSize

        context.coordinator.scrollView = scroll
        context.coordinator.contentView = content
        context.coordinator.backgroundView = background
        context.coordinator.imageObjectLayer = imageObjectLayer
        context.coordinator.imageObjectInteractionView = imageObjectInteraction
        context.coordinator.onImageObjectSelectionChanged = onImageObjectSelectionChanged
        context.coordinator.onImageObjectsCommitted = onImageObjectsCommitted
        context.coordinator.measurementGridView = measurementGrid
        context.coordinator.canvas = canvas
        context.coordinator.activeToolController = activeToolController
        context.coordinator.documentToken = documentToken
        context.coordinator.documentIdentifier = documentIdentifier
        context.coordinator.logicalCanvasSize = logicalCanvasSize
        context.coordinator.activeTool = tool
        context.coordinator.zoom100RequestToken = zoom100RequestToken
        context.coordinator.configureQuickToolGestures(
            activeToolController: activeToolController,
            onPencilContactBegan: onPencilContactBegan,
            onSinglePencilTap: onPencilSingleTap,
            onDoublePencilTap: onPencilDoubleTap
        )
        context.coordinator.quickToolGestureController.attach(
            to: content,
            coordinateView: scroll
        )
        context.coordinator.quickToolGestureController.setPalettePresented(
            quickToolPalettePresented
        )

        activeToolController.attach(canvas: canvas, backgroundView: background)

        DispatchQueue.main.async {
            context.coordinator.setZoomTo100Percent()
            context.coordinator.onUndoManagerChanged(canvas.undoManager)
            context.coordinator.reportZoom()
        }
        return scroll
    }

    func updateUIView(_ scroll: UIScrollView, context: Context) {
        let coordinator = context.coordinator
        coordinator.onDrawingChanged = onDrawingChanged
        coordinator.onUndoManagerChanged = onUndoManagerChanged
        coordinator.onZoomChanged = onZoomChanged
        coordinator.onImageObjectSelectionChanged = onImageObjectSelectionChanged
        coordinator.onImageObjectsCommitted = onImageObjectsCommitted
        coordinator.activeToolController = activeToolController
        coordinator.configureQuickToolGestures(
            activeToolController: activeToolController,
            onPencilContactBegan: onPencilContactBegan,
            onSinglePencilTap: onPencilSingleTap,
            onDoublePencilTap: onPencilDoubleTap
        )
        coordinator.quickToolGestureController.setPalettePresented(
            quickToolPalettePresented
        )

        coordinator.imageObjectLayer?.setObjects(imageObjects)
        coordinator.imageObjectInteractionView?.setState(
            objects: imageObjects,
            selectedID: selectedImageObjectID,
            selectionEnabled: tool == .lasso,
            zoomScale: scroll.zoomScale
        )

        if !activeToolController.isRasterEditing {
            coordinator.backgroundView?.image = backgroundImage
        }

        if let canvas = coordinator.canvas, let background = coordinator.backgroundView {
            activeToolController.attach(canvas: canvas, backgroundView: background)
        }

        coordinator.measurementGridView?.showGrid = showMeasurementGrid
        coordinator.measurementGridView?.showRulers = showMeasurementRulers
        coordinator.measurementGridView?.isHidden =
            !showMeasurementGrid && !showMeasurementRulers

        let sizeChanged = coordinator.logicalCanvasSize != logicalCanvasSize
        let documentChanged = coordinator.documentIdentifier != documentIdentifier
        let toolChanged = coordinator.activeTool != tool
        let zoom100Requested =
            coordinator.zoom100RequestToken != zoom100RequestToken
        let previousViewport = coordinator.captureViewport()
        let historyRestoreRequested = coordinator.consumeHistoryRestoreRequest(
            drawing: drawing,
            activeToolController: activeToolController
        )

        if sizeChanged {
            coordinator.logicalCanvasSize = logicalCanvasSize
            let frame = CGRect(origin: .zero, size: logicalCanvasSize)
            coordinator.contentView?.frame = frame
            coordinator.backgroundView?.frame = frame
            coordinator.imageObjectLayer?.frame = frame
            coordinator.imageObjectInteractionView?.frame = frame
            coordinator.measurementGridView?.frame = frame
            coordinator.canvas?.frame = frame
            coordinator.canvas?.contentSize = logicalCanvasSize
            coordinator.canvas?.contentInset = .zero
            coordinator.canvas?.contentOffset = .zero
            scroll.contentSize = logicalCanvasSize
        }

        let documentTokenChanged = coordinator.documentToken != documentToken
        if documentTokenChanged || historyRestoreRequested {
            if documentTokenChanged {
                coordinator.documentToken = documentToken
                coordinator.documentIdentifier = documentIdentifier
                coordinator.imageObjectInteractionView?.clearSelection(notify: false)
            }
            coordinator.replaceCanvas(
                drawing: drawing,
                activeToolController: activeToolController
            )

            if documentChanged {
                DispatchQueue.main.async {
                    coordinator.setZoomTo100Percent()
                }
            } else {
                DispatchQueue.main.async {
                    coordinator.restoreViewportAfterCanvasResize(previousViewport)
                }
            }
        } else if sizeChanged {
            DispatchQueue.main.async {
                coordinator.restoreViewportAfterCanvasResize(previousViewport)
            }
        }

        if toolChanged {
            coordinator.activeTool = tool
            if tool != .lasso {
                coordinator.imageObjectInteractionView?.clearSelection(notify: true)
            }
        }

        if zoom100Requested {
            coordinator.zoom100RequestToken = zoom100RequestToken
            DispatchQueue.main.async {
                coordinator.setZoomTo100Percent()
            }
        }
    }

    static func dismantleUIView(_ uiView: UIScrollView, coordinator: Coordinator) {
        coordinator.quickToolGestureController.detach()
    }

    final class Coordinator:
        NSObject,
        PKCanvasViewDelegate,
        UIScrollViewDelegate,
        LassoDrawingMutationHost
    {
        struct ViewportSnapshot {
            let zoomScale: CGFloat
            let normalizedCenter: CGPoint
        }

        weak var scrollView: UIScrollView?
        weak var canvas: PKCanvasView?
        weak var contentView: UIView?
        weak var backgroundView: UIImageView?
        weak var imageObjectLayer: CanvasImageObjectLayerView?
        weak var imageObjectInteractionView: CanvasImageObjectInteractionView?
        weak var measurementGridView: MeasurementGridView?
        weak var activeToolController: ActiveDrawingToolController?

        let historyRebaseController = PencilCanvasHistoryRebaseController()
        let quickToolGestureController = PencilQuickToolPaletteGestureController()
        private var pendingHistoryCanvasReplacement = false

        var documentToken = -1
        var documentIdentifier = ""
        var logicalCanvasSize = CGSize(width: 1600, height: 1000)
        var loading = false
        var activeTool: GraphicTool = .pencil
        var zoom100RequestToken = 0

        var onDrawingChanged: (PKDrawing) -> Void
        var onUndoManagerChanged: (UndoManager?) -> Void
        var onZoomChanged: (CGFloat) -> Void
        var onImageObjectSelectionChanged: (UUID?) -> Void = { _ in }
        var onImageObjectsCommitted: ([CanvasImageObject], UUID?, String) -> Void = {
            _, _, _ in
        }

        init(
            onDrawingChanged: @escaping (PKDrawing) -> Void,
            onUndoManagerChanged: @escaping (UndoManager?) -> Void,
            onZoomChanged: @escaping (CGFloat) -> Void
        ) {
            self.onDrawingChanged = onDrawingChanged
            self.onUndoManagerChanged = onUndoManagerChanged
            self.onZoomChanged = onZoomChanged
        }

        func configureQuickToolGestures(
            activeToolController: ActiveDrawingToolController,
            onPencilContactBegan: @escaping (CGPoint) -> Void,
            onSinglePencilTap: @escaping (CGPoint) -> Void,
            onDoublePencilTap: @escaping (CGPoint) -> Void
        ) {
            quickToolGestureController.onPencilContactBegan = {
                [weak controller = activeToolController] point in
                controller?.beginQuickToolTapCandidate()
                onPencilContactBegan(point)
            }
            quickToolGestureController.onDoubleTapRejected = {
                [weak controller = activeToolController] in
                controller?.discardQuickToolTapCandidate()
            }
            quickToolGestureController.onSinglePencilTap = {
                [weak controller = activeToolController] point in
                onSinglePencilTap(point)
                DispatchQueue.main.async {
                    _ = controller?.restoreQuickToolDismissalTapCandidate()
                }
            }
            quickToolGestureController.onDoublePencilTap = {
                [weak controller = activeToolController] point in
                DispatchQueue.main.async {
                    guard controller?.restoreQuickToolTapCandidate() == true else {
                        return
                    }
                    onDoublePencilTap(point)
                }
            }
        }

        func canvasViewDrawingDidChange(_ canvasView: PKCanvasView) {
            guard !loading else { return }
            if let activeToolController,
               activeToolController.consumeProgrammaticDrawingChange(canvasView.drawing) {
                pendingHistoryCanvasReplacement = true
                return
            }
            onDrawingChanged(canvasView.drawing)
            onUndoManagerChanged(canvasView.undoManager)
        }

        func consumeHistoryRestoreRequest(
            drawing: PKDrawing,
            activeToolController: ActiveDrawingToolController
        ) -> Bool {
            if activeToolController.consumeProgrammaticDrawingChange(drawing) {
                pendingHistoryCanvasReplacement = true
            }
            let requested = pendingHistoryCanvasReplacement
            pendingHistoryCanvasReplacement = false
            return requested
        }

        func replaceCanvas(
            drawing: PKDrawing,
            activeToolController: ActiveDrawingToolController
        ) {
            guard let currentCanvas = canvas,
                  let contentView,
                  let backgroundView else {
                return
            }

            let replacement = historyRebaseController.replaceCanvas(
                currentCanvas,
                in: contentView,
                below: imageObjectInteractionView,
                drawing: drawing,
                delegate: self
            )
            canvas = replacement
            activeToolController.attach(
                canvas: replacement,
                backgroundView: backgroundView
            )
            onUndoManagerChanged(replacement.undoManager)
        }

        /// Applies a unified lasso preview without treating each drag sample as a new edit.
        func applyLassoDrawing(_ drawing: PKDrawing, to canvas: PKCanvasView) {
            guard self.canvas === canvas else { return }
            loading = true
            canvas.drawing = drawing
            loading = false
        }

        func viewForZooming(in scrollView: UIScrollView) -> UIView? {
            contentView
        }

        func scrollViewDidZoom(_ scrollView: UIScrollView) {
            centerCanvas()
            imageObjectInteractionView?.updateZoom(scrollView.zoomScale)
            reportZoom()
        }

        /// Sets the viewport to exactly 100% and top-left.
        func setZoomTo100Percent() {
            guard let scroll = scrollView else { return }
            scroll.minimumZoomScale = min(scroll.minimumZoomScale, 0.05)
            scroll.maximumZoomScale = max(scroll.maximumZoomScale, 10.0)
            scroll.setZoomScale(1.0, animated: false)
            centerCanvas()
            scroll.contentOffset = CGPoint(
                x: -scroll.contentInset.left,
                y: -scroll.contentInset.top
            )
            imageObjectInteractionView?.updateZoom(scroll.zoomScale)
            reportZoom()
        }

        func captureViewport() -> ViewportSnapshot {
            guard let scroll = scrollView,
                  scroll.contentSize.width > 0,
                  scroll.contentSize.height > 0 else {
                return ViewportSnapshot(
                    zoomScale: 1.0,
                    normalizedCenter: CGPoint(x: 0.5, y: 0.5)
                )
            }

            let centerX = scroll.contentOffset.x + scroll.bounds.width / 2
            let centerY = scroll.contentOffset.y + scroll.bounds.height / 2
            return ViewportSnapshot(
                zoomScale: scroll.zoomScale,
                normalizedCenter: CGPoint(
                    x: min(max(centerX / scroll.contentSize.width, 0), 1),
                    y: min(max(centerY / scroll.contentSize.height, 0), 1)
                )
            )
        }

        func restoreViewportAfterCanvasResize(_ snapshot: ViewportSnapshot) {
            guard let scroll = scrollView else { return }
            let preservedZoom = min(
                max(snapshot.zoomScale, scroll.minimumZoomScale),
                scroll.maximumZoomScale
            )
            scroll.setZoomScale(preservedZoom, animated: false)
            centerCanvas()

            let targetCenter = CGPoint(
                x: scroll.contentSize.width * snapshot.normalizedCenter.x,
                y: scroll.contentSize.height * snapshot.normalizedCenter.y
            )
            let proposedOffset = CGPoint(
                x: targetCenter.x - scroll.bounds.width / 2,
                y: targetCenter.y - scroll.bounds.height / 2
            )
            scroll.contentOffset = clampedContentOffset(
                proposedOffset,
                in: scroll
            )
            imageObjectInteractionView?.updateZoom(scroll.zoomScale)
            reportZoom()
        }

        private func clampedContentOffset(
            _ proposed: CGPoint,
            in scroll: UIScrollView
        ) -> CGPoint {
            let minimumX = -scroll.contentInset.left
            let minimumY = -scroll.contentInset.top
            let maximumX = max(
                minimumX,
                scroll.contentSize.width - scroll.bounds.width
                    + scroll.contentInset.right
            )
            let maximumY = max(
                minimumY,
                scroll.contentSize.height - scroll.bounds.height
                    + scroll.contentInset.bottom
            )
            return CGPoint(
                x: min(max(proposed.x, minimumX), maximumX),
                y: min(max(proposed.y, minimumY), maximumY)
            )
        }

        func fitCanvas(reset: Bool) {
            guard let scroll = scrollView,
                  scroll.bounds.width > 1,
                  scroll.bounds.height > 1,
                  logicalCanvasSize.width > 1,
                  logicalCanvasSize.height > 1 else {
                return
            }

            let fit = min(
                scroll.bounds.width / logicalCanvasSize.width,
                scroll.bounds.height / logicalCanvasSize.height
            )
            let safeFit = max(fit, 0.05)
            scroll.minimumZoomScale = max(safeFit * 0.5, 0.05)
            scroll.maximumZoomScale = max(safeFit * 10.0, 5.0)

            if reset {
                scroll.setZoomScale(safeFit, animated: false)
                scroll.contentOffset = .zero
            }
            centerCanvas()
            reportZoom()
        }

        func centerCanvas() {
            guard let scroll = scrollView else { return }
            let horizontal = max(
                (scroll.bounds.width - scroll.contentSize.width) / 2,
                0
            )
            let vertical = max(
                (scroll.bounds.height - scroll.contentSize.height) / 2,
                0
            )
            scroll.contentInset = UIEdgeInsets(
                top: vertical,
                left: horizontal,
                bottom: vertical,
                right: horizontal
            )
        }

        func reportZoom() {
            guard let scroll = scrollView else { return }
            onZoomChanged(scroll.zoomScale)
        }
    }
}
