// Hosts the PencilKit canvas, viewport zoom with explicit 100% reset, two-finger undo, lasso selection, and proportional selection resizing.
// ND_MIND_MIRROR_IPAD_LAYOUT_20260823

import PencilKit
import SwiftUI
import UIKit

/// Draws a touch-through selection frame with four finger-draggable proportional resize handles.
final class SelectionResizeOverlay: UIView {
    /// Names one corner of the active selection rectangle.
    enum Corner: Int, CaseIterable {
        case topLeft = 0
        case topRight = 1
        case bottomLeft = 2
        case bottomRight = 3
    }

    private let borderLayer = CAShapeLayer()
    let handles: [UIView]
    let moveHandle: UIView
    private var selectionBounds: CGRect?
    private var zoomScale: CGFloat = 1.0

    /// Creates the thin border and its four circular handles.
    override init(frame: CGRect) {
        // ND_SELECTION_MOVE_HANDLE_V1
        handles = Corner.allCases.map { corner in
            let handle = UIView()
            handle.tag = corner.rawValue
            handle.backgroundColor = .systemBackground
            handle.layer.borderColor = UIColor.systemBlue.cgColor
            handle.isUserInteractionEnabled = true
            return handle
        }
        moveHandle = UIView()
        super.init(frame: frame)
        backgroundColor = .clear
        isOpaque = false
        isHidden = true
        borderLayer.fillColor = UIColor.clear.cgColor
        borderLayer.strokeColor = UIColor.systemBlue.cgColor
        layer.addSublayer(borderLayer)
        for handle in handles {
            addSubview(handle)
        }
        moveHandle.backgroundColor = UIColor.systemGray3.withAlphaComponent(0.72)
        moveHandle.layer.borderColor = UIColor.systemGray5.cgColor
        moveHandle.layer.borderWidth = 1.5
        moveHandle.isUserInteractionEnabled = true
        addSubview(moveHandle)
    }

    /// Supports UIKit construction only; Interface Builder is not used by the Swift package.
    required init?(coder: NSCoder) {
        nil
    }

    /// Shows a selection rectangle using logical canvas coordinates.
    func setSelection(bounds: CGRect, zoomScale: CGFloat) {
        selectionBounds = bounds.standardized
        self.zoomScale = max(zoomScale, 0.05)
        isHidden = false
        setNeedsLayout()
    }

    /// Updates handle sizes after a canvas pinch without changing the logical selection.
    func updateZoom(_ zoomScale: CGFloat) {
        self.zoomScale = max(zoomScale, 0.05)
        if selectionBounds != nil {
            setNeedsLayout()
        }
    }

    /// Hides the frame because no usable lasso selection remains.
    func clearSelection() {
        selectionBounds = nil
        isHidden = true
        borderLayer.path = nil
    }

    /// Returns one logical corner point of the currently displayed rectangle.
    func cornerPoint(_ corner: Corner) -> CGPoint? {
        guard let bounds = selectionBounds else { return nil }
        switch corner {
        case .topLeft:
            return CGPoint(x: bounds.minX, y: bounds.minY)
        case .topRight:
            return CGPoint(x: bounds.maxX, y: bounds.minY)
        case .bottomLeft:
            return CGPoint(x: bounds.minX, y: bounds.maxY)
        case .bottomRight:
            return CGPoint(x: bounds.maxX, y: bounds.maxY)
        }
    }

    /// Returns the corner diagonally opposite the supplied corner.
    static func opposite(_ corner: Corner) -> Corner {
        switch corner {
        case .topLeft: return .bottomRight
        case .topRight: return .bottomLeft
        case .bottomLeft: return .topRight
        case .bottomRight: return .topLeft
        }
    }

    /// Keeps the border thin and the handles roughly 28 screen points regardless of zoom.
    override func layoutSubviews() {
        super.layoutSubviews()
        guard let bounds = selectionBounds else { return }
        let scale = max(zoomScale, 0.05)
        let lineWidth = max(1.8 / scale, 0.45)
        let handleDiameter = 28.0 / scale
        borderLayer.frame = self.bounds
        borderLayer.lineWidth = lineWidth
        borderLayer.path = UIBezierPath(rect: bounds).cgPath

        let moveWidth = 34.0 / scale
        let moveHeight = 18.0 / scale
        moveHandle.bounds = CGRect(x: 0, y: 0, width: moveWidth, height: moveHeight)
        moveHandle.center = CGPoint(
            x: bounds.midX,
            y: max(moveHeight / 2, bounds.minY - 13.0 / scale)
        )
        moveHandle.layer.cornerRadius = moveHeight / 2
        moveHandle.layer.borderWidth = max(1.5 / scale, 0.6)

        for corner in Corner.allCases {
            let handle = handles[corner.rawValue]
            guard let center = cornerPoint(corner) else { continue }
            handle.bounds = CGRect(x: 0, y: 0, width: handleDiameter, height: handleDiameter)
            handle.center = center
            handle.layer.cornerRadius = handleDiameter / 2
            handle.layer.borderWidth = max(1.6 / scale, 0.6)
        }
    }

    /// Lets PencilKit receive all touches except direct touches on resize handles.
    override func hitTest(_ point: CGPoint, with event: UIEvent?) -> UIView? {
        guard !isHidden else { return nil }
        let movePoint = moveHandle.convert(point, from: self)
        if moveHandle.point(inside: movePoint, with: event) {
            return moveHandle
        }
        for handle in handles.reversed() {
            let localPoint = handle.convert(point, from: self)
            if handle.point(inside: localPoint, with: event) {
                return handle
            }
        }
        return nil
    }
}

/// Pencil canvas inside a UIScrollView where Pencil draws/selects while fingers pan, pinch, and resize selections.
struct PencilCanvasView: UIViewRepresentable {
    let drawing: PKDrawing
    let backgroundImage: UIImage?
    let documentToken: Int
    let documentIdentifier: String
    let tool: GraphicTool
    let color: Color
    let width: Double
    let opacity: Double
    let imageObjects: [CanvasImageObject]
    let selectedImageObjectID: UUID?
    let logicalCanvasSize: CGSize
    let showMeasurementGrid: Bool
    let showMeasurementRulers: Bool
    let zoom100RequestToken: Int
    let onDrawingChanged: (PKDrawing) -> Void
    let onUndoManagerChanged: (UndoManager?) -> Void
    let onZoomChanged: (CGFloat) -> Void
    let onImageObjectSelectionChanged: (UUID?) -> Void
    let onImageObjectsCommitted: ([CanvasImageObject], UUID?, String) -> Void

    /// Creates the coordinator that owns PencilKit, lasso observation, resize, and UIScrollView callbacks.
    func makeCoordinator() -> Coordinator {
        Coordinator(
            onDrawingChanged: onDrawingChanged,
            onUndoManagerChanged: onUndoManagerChanged,
            onZoomChanged: onZoomChanged
        )
    }

    /// Builds the scroll view, background, PencilKit canvas, resize overlay, and gesture recognizers.
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
        scroll.minimumZoomScale = 0.05
        scroll.maximumZoomScale = 10.0

        let content = UIView(frame: CGRect(origin: .zero, size: logicalCanvasSize))
        content.backgroundColor = .white

        let background = UIImageView(frame: content.bounds)
        background.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        background.contentMode = .scaleAspectFit
        background.backgroundColor = .white
        background.image = backgroundImage
        content.addSubview(background)

        // ND_CANVAS_IMAGE_LAYER_V1
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

        let canvas = PKCanvasView(frame: content.bounds)
        canvas.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        canvas.backgroundColor = .clear
        canvas.isOpaque = false
        canvas.drawingPolicy = .pencilOnly
        canvas.isScrollEnabled = false
        canvas.bounces = false
        canvas.contentInset = .zero
        canvas.contentOffset = .zero
        canvas.contentSize = logicalCanvasSize
        canvas.minimumZoomScale = 1.0
        canvas.maximumZoomScale = 1.0
        canvas.zoomScale = 1.0
        canvas.delegate = context.coordinator
        canvas.drawing = drawing
        content.addSubview(canvas)

        // ND_CANVAS_IMAGE_INTERACTION_V1
        let imageObjectInteraction = CanvasImageObjectInteractionView(frame: content.bounds)
        imageObjectInteraction.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        imageObjectInteraction.onSelectionChanged = { id in
            context.coordinator.clearSelection()
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

        let selectionOverlay = SelectionResizeOverlay(frame: content.bounds)
        selectionOverlay.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        content.addSubview(selectionOverlay)

        scroll.addSubview(content)
        scroll.contentSize = logicalCanvasSize

        let lassoObserver = UIPanGestureRecognizer(
            target: context.coordinator,
            action: #selector(Coordinator.handleLassoObservation(_:))
        )
        lassoObserver.allowedTouchTypes = [NSNumber(value: UITouch.TouchType.pencil.rawValue)]
        lassoObserver.maximumNumberOfTouches = 1
        lassoObserver.cancelsTouchesInView = false
        lassoObserver.delegate = context.coordinator
        canvas.addGestureRecognizer(lassoObserver)

        for handle in selectionOverlay.handles {
            let resize = UIPanGestureRecognizer(
                target: context.coordinator,
                action: #selector(Coordinator.handleResize(_:))
            )
            resize.maximumNumberOfTouches = 1
            resize.allowedTouchTypes = [NSNumber(value: UITouch.TouchType.direct.rawValue)]
            resize.delegate = context.coordinator
            handle.addGestureRecognizer(resize)
            scroll.panGestureRecognizer.require(toFail: resize)
        }

        let moveSelection = UIPanGestureRecognizer(
            target: context.coordinator,
            action: #selector(Coordinator.handleMoveSelection(_:))
        )
        moveSelection.maximumNumberOfTouches = 1
        moveSelection.allowedTouchTypes = [NSNumber(value: UITouch.TouchType.direct.rawValue)]
        moveSelection.delegate = context.coordinator
        selectionOverlay.moveHandle.addGestureRecognizer(moveSelection)
        scroll.panGestureRecognizer.require(toFail: moveSelection)

        let twoFingerUndo = UITapGestureRecognizer(
            target: context.coordinator,
            action: #selector(Coordinator.handleTwoFingerUndo(_:))
        )
        twoFingerUndo.numberOfTouchesRequired = 2
        twoFingerUndo.numberOfTapsRequired = 1
        twoFingerUndo.cancelsTouchesInView = false
        scroll.addGestureRecognizer(twoFingerUndo)

        context.coordinator.scrollView = scroll
        context.coordinator.contentView = content
        context.coordinator.backgroundView = background
        context.coordinator.imageObjectLayer = imageObjectLayer
        context.coordinator.imageObjectInteractionView = imageObjectInteraction
        context.coordinator.onImageObjectSelectionChanged = onImageObjectSelectionChanged
        context.coordinator.onImageObjectsCommitted = onImageObjectsCommitted
        context.coordinator.measurementGridView = measurementGrid
        context.coordinator.canvas = canvas
        context.coordinator.selectionOverlay = selectionOverlay
        context.coordinator.lassoObserver = lassoObserver
        context.coordinator.documentToken = documentToken
        context.coordinator.documentIdentifier = documentIdentifier
        context.coordinator.logicalCanvasSize = logicalCanvasSize
        context.coordinator.activeTool = tool
        context.coordinator.zoom100RequestToken = zoom100RequestToken
        applyTool(canvas, coordinator: context.coordinator)

        DispatchQueue.main.async {
            context.coordinator.setZoomTo100Percent()
            context.coordinator.onUndoManagerChanged(canvas.undoManager)
            context.coordinator.reportZoom()
        }
        return scroll
    }

    /// Synchronizes drawing, canvas size, callbacks, background, tool, selection, zoom requests, and viewport without unnecessary resets.
    func updateUIView(_ scroll: UIScrollView, context: Context) {
        let coordinator = context.coordinator
        coordinator.onDrawingChanged = onDrawingChanged
        coordinator.onUndoManagerChanged = onUndoManagerChanged
        coordinator.onZoomChanged = onZoomChanged
        coordinator.onImageObjectSelectionChanged = onImageObjectSelectionChanged
        coordinator.onImageObjectsCommitted = onImageObjectsCommitted
        coordinator.imageObjectLayer?.setObjects(imageObjects)
        coordinator.imageObjectInteractionView?.setState(
            objects: imageObjects,
            selectedID: selectedImageObjectID,
            selectionEnabled: tool == .lasso,
            zoomScale: scroll.zoomScale
        )
        coordinator.backgroundView?.image = backgroundImage
        coordinator.measurementGridView?.showGrid = showMeasurementGrid
        coordinator.measurementGridView?.showRulers = showMeasurementRulers
        coordinator.measurementGridView?.isHidden = !showMeasurementGrid && !showMeasurementRulers

        let sizeChanged = coordinator.logicalCanvasSize != logicalCanvasSize
        let documentChanged = coordinator.documentIdentifier != documentIdentifier
        let toolChanged = coordinator.activeTool != tool
        let zoom100Requested = coordinator.zoom100RequestToken != zoom100RequestToken

        if sizeChanged {
            coordinator.logicalCanvasSize = logicalCanvasSize
            coordinator.contentView?.frame = CGRect(origin: .zero, size: logicalCanvasSize)
            coordinator.backgroundView?.frame = CGRect(origin: .zero, size: logicalCanvasSize)
            coordinator.imageObjectLayer?.frame = CGRect(origin: .zero, size: logicalCanvasSize)
            coordinator.imageObjectInteractionView?.frame = CGRect(origin: .zero, size: logicalCanvasSize)
            coordinator.measurementGridView?.frame = CGRect(origin: .zero, size: logicalCanvasSize)
            coordinator.canvas?.frame = CGRect(origin: .zero, size: logicalCanvasSize)
            coordinator.canvas?.contentSize = logicalCanvasSize
            coordinator.canvas?.contentInset = .zero
            coordinator.canvas?.contentOffset = .zero
            coordinator.selectionOverlay?.frame = CGRect(origin: .zero, size: logicalCanvasSize)
            scroll.contentSize = logicalCanvasSize
        }

        if coordinator.documentToken != documentToken {
            coordinator.documentToken = documentToken
            coordinator.documentIdentifier = documentIdentifier
            coordinator.clearSelection()
            coordinator.loading = true
            coordinator.canvas?.drawing = drawing
            coordinator.loading = false
            if documentChanged || sizeChanged {
                DispatchQueue.main.async { coordinator.setZoomTo100Percent() }
            } else {
                DispatchQueue.main.async {
                    coordinator.centerCanvas()
                    coordinator.reportZoom()
                }
            }
        } else if sizeChanged {
            coordinator.clearSelection()
            DispatchQueue.main.async { coordinator.setZoomTo100Percent() }
        }

        if toolChanged {
            coordinator.activeTool = tool
            if tool != .lasso {
                coordinator.clearSelection()
                coordinator.imageObjectInteractionView?.clearSelection(notify: true)
            }
        }

        if zoom100Requested {
            coordinator.zoom100RequestToken = zoom100RequestToken
            DispatchQueue.main.async {
                coordinator.setZoomTo100Percent()
            }
        }

        if let canvas = coordinator.canvas {
            applyTool(canvas, coordinator: coordinator)
        }
    }

    /// Applies the selected Pencil, Highlighter, Eraser, or native Lasso tool to PencilKit.
    private func applyTool(_ canvas: PKCanvasView, coordinator: Coordinator) {
        switch tool {
        case .pencil:
            canvas.tool = PKInkingTool(
                .pencil,
                color: UIColor(color).withAlphaComponent(CGFloat(min(max(opacity, 0.05), 1.0))),
                width: CGFloat(max(0.5, width))
            )
        case .highlighter:
            canvas.tool = PKInkingTool(
                .marker,
                color: UIColor(color).withAlphaComponent(CGFloat(min(max(opacity, 0.05), 1.0))),
                width: CGFloat(max(0.5, width))
            )
        case .eraser:
            canvas.tool = PKEraserTool(.vector)
        case .lasso:
            canvas.tool = PKLassoTool()
        }
        coordinator.lassoObserver?.isEnabled = tool == .lasso
    }

    /// Coordinates drawing changes, viewport zoom, lasso geometry, proportional resizing, and Undo/Redo.
    final class Coordinator: NSObject, PKCanvasViewDelegate, UIScrollViewDelegate, UIGestureRecognizerDelegate {
        /// Captures one resize drag so every frame is derived from the same unmodified drawing.
        private struct MoveSession {
            let originalDrawing: PKDrawing
            let selectedIndices: [Int]
            let originalBounds: CGRect
        }

        private struct ResizeSession {
            let originalDrawing: PKDrawing
            let selectedIndices: [Int]
            let originalBounds: CGRect
            let corner: SelectionResizeOverlay.Corner
            let fixedPoint: CGPoint
            let originalCornerPoint: CGPoint
        }

        weak var scrollView: UIScrollView?
        weak var canvas: PKCanvasView?
        weak var contentView: UIView?
        weak var backgroundView: UIImageView?
        weak var imageObjectLayer: CanvasImageObjectLayerView?
        weak var imageObjectInteractionView: CanvasImageObjectInteractionView?
        weak var measurementGridView: MeasurementGridView?
        weak var selectionOverlay: SelectionResizeOverlay?
        weak var lassoObserver: UIPanGestureRecognizer?
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
        var onImageObjectsCommitted: ([CanvasImageObject], UUID?, String) -> Void = { _, _, _ in }

        private var lassoPoints: [CGPoint] = []
        private var selectedStrokeIndices: [Int] = []
        private var resizeSession: ResizeSession?
        private var moveSession: MoveSession?

        /// Stores callbacks used by PencilKit and scroll-view delegates.
        init(
            onDrawingChanged: @escaping (PKDrawing) -> Void,
            onUndoManagerChanged: @escaping (UndoManager?) -> Void,
            onZoomChanged: @escaping (CGFloat) -> Void
        ) {
            self.onDrawingChanged = onDrawingChanged
            self.onUndoManagerChanged = onUndoManagerChanged
            self.onZoomChanged = onZoomChanged
        }

        /// Publishes PencilKit drawing changes and keeps an existing index-based selection frame attached to moved strokes.
        func canvasViewDrawingDidChange(_ canvasView: PKCanvasView) {
            guard !loading else { return }
            if resizeSession == nil && moveSession == nil && !selectedStrokeIndices.isEmpty {
                refreshSelectionBounds()
            }
            onDrawingChanged(canvasView.drawing)
            onUndoManagerChanged(canvasView.undoManager)
        }

        /// Returns the logical canvas container that UIScrollView should zoom.
        func viewForZooming(in scrollView: UIScrollView) -> UIView? { contentView }

        /// Recenters the canvas, resizes selection handles, and reports zoom after each pinch update.
        func scrollViewDidZoom(_ scrollView: UIScrollView) {
            centerCanvas()
            selectionOverlay?.updateZoom(scrollView.zoomScale)
            imageObjectInteractionView?.updateZoom(scrollView.zoomScale)
            reportZoom()
        }

        /// Allows the passive Pencil lasso observer to run beside PencilKit's native lasso recognizers.
        func gestureRecognizer(
            _ gestureRecognizer: UIGestureRecognizer,
            shouldRecognizeSimultaneouslyWith otherGestureRecognizer: UIGestureRecognizer
        ) -> Bool {
            if gestureRecognizer === lassoObserver || otherGestureRecognizer === lassoObserver {
                return true
            }
            return false
        }

        /// Undoes exactly one PencilKit or custom resize operation on a two-finger tap.
        @objc func handleTwoFingerUndo(_ recognizer: UITapGestureRecognizer) {
            guard recognizer.state == .ended, let canvas else { return }
            canvas.undoManager?.undo()
            refreshSelectionBounds()
            onUndoManagerChanged(canvas.undoManager)
        }

        /// Passively records the Apple Pencil lasso path, then derives selected stroke indices without newer PencilKit selection APIs.
        @objc func handleLassoObservation(_ recognizer: UIPanGestureRecognizer) {
            guard activeTool == .lasso, let canvas else { return }
            switch recognizer.state {
            case .began:
                imageObjectInteractionView?.clearSelection(notify: true)
                lassoPoints = [recognizer.location(in: canvas)]
            case .changed:
                let point = recognizer.location(in: canvas)
                if let last = lassoPoints.last {
                    let dx = point.x - last.x
                    let dy = point.y - last.y
                    if dx * dx + dy * dy < 4.0 {
                        return
                    }
                }
                lassoPoints.append(point)
            case .ended:
                lassoPoints.append(recognizer.location(in: canvas))
                updateSelectionFromLasso(canvas.drawing)
                lassoPoints.removeAll(keepingCapacity: true)
            case .cancelled, .failed:
                lassoPoints.removeAll(keepingCapacity: true)
            default:
                break
            }
        }

        /// Moves the entire current lasso selection by dragging the blue pill handle.
        @objc func handleMoveSelection(_ recognizer: UIPanGestureRecognizer) {
            guard activeTool == .lasso,
                  let overlay = selectionOverlay,
                  let canvas = canvas,
                  let bounds = currentSelectionBounds(in: canvas.drawing),
                  !selectedStrokeIndices.isEmpty else { return }

            switch recognizer.state {
            case .began:
                moveSession = MoveSession(
                    originalDrawing: canvas.drawing,
                    selectedIndices: selectedStrokeIndices,
                    originalBounds: bounds
                )
            case .changed, .ended:
                guard let session = moveSession else { return }
                let raw = recognizer.translation(in: overlay)
                let dx = min(
                    max(raw.x, -session.originalBounds.minX),
                    logicalCanvasSize.width - session.originalBounds.maxX
                )
                let dy = min(
                    max(raw.y, -session.originalBounds.minY),
                    logicalCanvasSize.height - session.originalBounds.maxY
                )
                applyMove(
                    dx: dx,
                    dy: dy,
                    session: session,
                    canvas: canvas,
                    overlay: overlay
                )
                if recognizer.state == .ended {
                    let finalDrawing = canvas.drawing
                    moveSession = nil
                    registerMoveUndo(original: session.originalDrawing, final: finalDrawing)
                    onDrawingChanged(finalDrawing)
                    onUndoManagerChanged(canvas.undoManager)
                }
            case .cancelled, .failed:
                if let session = moveSession {
                    loading = true
                    canvas.drawing = session.originalDrawing
                    loading = false
                    moveSession = nil
                    refreshSelectionBounds()
                }
            default:
                break
            }
        }

        private func applyMove(
            dx: CGFloat,
            dy: CGFloat,
            session: MoveSession,
            canvas: PKCanvasView,
            overlay: SelectionResizeOverlay
        ) {
            let transform = CGAffineTransform(translationX: dx, y: dy)
            var selectedStrokes: [PKStroke] = []
            var validIndices: [Int] = []
            for index in session.selectedIndices
            where index >= 0 && index < session.originalDrawing.strokes.count {
                selectedStrokes.append(session.originalDrawing.strokes[index])
                validIndices.append(index)
            }
            guard !selectedStrokes.isEmpty else { return }

            var selectedDrawing = PKDrawing(strokes: selectedStrokes)
            selectedDrawing.transform(using: transform)
            var allStrokes = session.originalDrawing.strokes
            for (offset, index) in validIndices.enumerated()
            where offset < selectedDrawing.strokes.count {
                allStrokes[index] = selectedDrawing.strokes[offset]
            }
            loading = true
            canvas.drawing = PKDrawing(strokes: allStrokes)
            loading = false
            overlay.setSelection(
                bounds: session.originalBounds.offsetBy(dx: dx, dy: dy),
                zoomScale: scrollView?.zoomScale ?? 1.0
            )
        }

        /// Starts, updates, or commits one proportional resize drag from a circular corner handle.
        @objc func handleResize(_ recognizer: UIPanGestureRecognizer) {
            guard activeTool == .lasso,
                  let handle = recognizer.view,
                  let overlay = selectionOverlay,
                  let canvas = canvas,
                  let corner = SelectionResizeOverlay.Corner(rawValue: handle.tag),
                  !selectedStrokeIndices.isEmpty else { return }

            let point = recognizer.location(in: overlay)
            switch recognizer.state {
            case .began:
                guard let originalCorner = overlay.cornerPoint(corner),
                      let fixed = overlay.cornerPoint(SelectionResizeOverlay.opposite(corner)),
                      let bounds = currentSelectionBounds(in: canvas.drawing) else { return }
                resizeSession = ResizeSession(
                    originalDrawing: canvas.drawing,
                    selectedIndices: selectedStrokeIndices,
                    originalBounds: bounds,
                    corner: corner,
                    fixedPoint: fixed,
                    originalCornerPoint: originalCorner
                )
            case .changed:
                guard let session = resizeSession else { return }
                let scale = proportionalScale(currentPoint: point, session: session)
                applyResize(scale: scale, session: session, canvas: canvas, overlay: overlay)
            case .ended:
                guard let session = resizeSession else { return }
                let scale = proportionalScale(currentPoint: point, session: session)
                applyResize(scale: scale, session: session, canvas: canvas, overlay: overlay)
                let finalDrawing = canvas.drawing
                resizeSession = nil
                registerResizeUndo(original: session.originalDrawing, final: finalDrawing)
                onDrawingChanged(finalDrawing)
                onUndoManagerChanged(canvas.undoManager)
            case .cancelled, .failed:
                if let session = resizeSession {
                    loading = true
                    canvas.drawing = session.originalDrawing
                    loading = false
                    resizeSession = nil
                    refreshSelectionBounds()
                }
            default:
                break
            }
        }

        /// Chooses stroke indices whose path samples or rendered center fall inside the completed lasso polygon.
        private func updateSelectionFromLasso(_ drawing: PKDrawing) {
            guard lassoPoints.count >= 3 else {
                clearSelection()
                return
            }
            var selected: [Int] = []
            for (index, stroke) in drawing.strokes.enumerated() {
                let bounds = stroke.renderBounds
                var included = pointInPolygon(
                    CGPoint(x: bounds.midX, y: bounds.midY),
                    polygon: lassoPoints
                )
                if !included {
                    for point in stroke.path {
                        if pointInPolygon(point.location.applying(stroke.transform), polygon: lassoPoints) {
                            included = true
                            break
                        }
                    }
                }
                if included {
                    selected.append(index)
                }
            }
            selectedStrokeIndices = selected
            refreshSelectionBounds()
            if selected.isEmpty {
                imageObjectInteractionView?.selectObject(inLasso: lassoPoints)
            }
        }

        /// Uses an even-odd ray test for freeform lasso containment.
        private func pointInPolygon(_ point: CGPoint, polygon: [CGPoint]) -> Bool {
            guard polygon.count >= 3 else { return false }
            var inside = false
            var previous = polygon.count - 1
            for current in 0..<polygon.count {
                let a = polygon[current]
                let b = polygon[previous]
                let crosses = ((a.y > point.y) != (b.y > point.y))
                    && (point.x < (b.x - a.x) * (point.y - a.y) / ((b.y - a.y) == 0 ? 0.000001 : (b.y - a.y)) + a.x)
                if crosses { inside.toggle() }
                previous = current
            }
            return inside
        }

        /// Returns the union of render bounds for the currently selected stroke indices.
        private func currentSelectionBounds(in drawing: PKDrawing) -> CGRect? {
            var result: CGRect?
            for index in selectedStrokeIndices where index >= 0 && index < drawing.strokes.count {
                let bounds = drawing.strokes[index].renderBounds.standardized
                result = result.map { $0.union(bounds) } ?? bounds
            }
            guard let bounds = result, bounds.width > 0.5, bounds.height > 0.5 else { return nil }
            return bounds.insetBy(dx: -4, dy: -4)
        }

        /// Recomputes the frame from selected indices after lasso movement, Undo, or programmatic drawing changes.
        private func refreshSelectionBounds() {
            guard let canvas, let overlay = selectionOverlay,
                  let bounds = currentSelectionBounds(in: canvas.drawing) else {
                selectionOverlay?.clearSelection()
                return
            }
            overlay.setSelection(bounds: bounds, zoomScale: scrollView?.zoomScale ?? 1.0)
        }

        /// Clears index tracking and the visible selection frame.
        func clearSelection() {
            lassoPoints.removeAll(keepingCapacity: false)
            selectedStrokeIndices.removeAll(keepingCapacity: false)
            resizeSession = nil
            selectionOverlay?.clearSelection()
        }

        /// Projects the dragged corner onto the original diagonal so one scalar controls both axes.
        private func proportionalScale(currentPoint: CGPoint, session: ResizeSession) -> CGFloat {
            let originalX = session.originalCornerPoint.x - session.fixedPoint.x
            let originalY = session.originalCornerPoint.y - session.fixedPoint.y
            let currentX = currentPoint.x - session.fixedPoint.x
            let currentY = currentPoint.y - session.fixedPoint.y
            let denominator = originalX * originalX + originalY * originalY
            guard denominator > 0.0001 else { return 1.0 }
            let projected = (currentX * originalX + currentY * originalY) / denominator
            return min(max(projected, 0.08), 20.0)
        }

        // ND_MIGRATION4_PRESERVE_STROKE_THICKNESS
        /// Applies only geometry to a stroke while preserving each PencilKit control-point size.
        private func strokeByApplyingGeometryTransform(
            _ stroke: PKStroke,
            transform: CGAffineTransform
        ) -> PKStroke {
            let points = stroke.path.map { point in
                PKStrokePoint(
                    location: point.location.applying(stroke.transform).applying(transform),
                    timeOffset: point.timeOffset,
                    size: point.size,
                    opacity: point.opacity,
                    force: point.force,
                    azimuth: point.azimuth,
                    altitude: point.altitude
                )
            }
            let path = PKStrokePath(
                controlPoints: points,
                creationDate: Date()
            )
            return PKStroke(
                ink: stroke.ink,
                path: path,
                transform: .identity,
                mask: stroke.mask
            )
        }

        /// Applies one uniform transform to only the selected stroke indices while the opposite corner stays fixed.
        private func applyResize(
            scale: CGFloat,
            session: ResizeSession,
            canvas: PKCanvasView,
            overlay: SelectionResizeOverlay
        ) {
            var selectedStrokes: [PKStroke] = []
            var validIndices: [Int] = []
            for index in session.selectedIndices where index >= 0 && index < session.originalDrawing.strokes.count {
                selectedStrokes.append(session.originalDrawing.strokes[index])
                validIndices.append(index)
            }
            guard !selectedStrokes.isEmpty else { return }

            let fixed = session.fixedPoint
            let transform = CGAffineTransform(translationX: fixed.x, y: fixed.y)
                .scaledBy(x: scale, y: scale)
                .translatedBy(x: -fixed.x, y: -fixed.y)

            let selectedDrawing = PKDrawing(
                strokes: selectedStrokes.map {
                    strokeByApplyingGeometryTransform($0, transform: transform)
                }
            )
            var allStrokes = session.originalDrawing.strokes
            for (offset, index) in validIndices.enumerated() where offset < selectedDrawing.strokes.count {
                allStrokes[index] = selectedDrawing.strokes[offset]
            }
            let resizedDrawing = PKDrawing(strokes: allStrokes)
            loading = true
            canvas.drawing = resizedDrawing
            loading = false

            let resizedBounds = session.originalBounds.applying(transform).standardized
            overlay.setSelection(bounds: resizedBounds, zoomScale: scrollView?.zoomScale ?? 1.0)
        }

        private func registerMoveUndo(original: PKDrawing, final: PKDrawing) {
            guard let manager = canvas?.undoManager else { return }
            manager.registerUndo(withTarget: self) { target in
                target.restoreDrawingForMove(original, reciprocal: final)
            }
            manager.setActionName("Move Selection")
        }

        private func restoreDrawingForMove(_ drawing: PKDrawing, reciprocal: PKDrawing) {
            guard let canvas else { return }
            loading = true
            canvas.drawing = drawing
            loading = false
            canvas.undoManager?.registerUndo(withTarget: self) { target in
                target.restoreDrawingForMove(reciprocal, reciprocal: drawing)
            }
            canvas.undoManager?.setActionName("Move Selection")
            refreshSelectionBounds()
            onDrawingChanged(drawing)
            onUndoManagerChanged(canvas.undoManager)
        }

        /// Registers a custom resize as one Undo/Redo operation after the finger drag finishes.
        private func registerResizeUndo(original: PKDrawing, final: PKDrawing) {
            guard let manager = canvas?.undoManager else { return }
            manager.registerUndo(withTarget: self) { target in
                target.restoreDrawingForResize(original, reciprocal: final)
            }
            manager.setActionName("Resize Selection")
        }

        /// Restores one drawing and registers its reciprocal state so UIKit automatically supplies Redo.
        private func restoreDrawingForResize(_ drawing: PKDrawing, reciprocal: PKDrawing) {
            guard let canvas else { return }
            loading = true
            canvas.drawing = drawing
            loading = false
            canvas.undoManager?.registerUndo(withTarget: self) { target in
                target.restoreDrawingForResize(reciprocal, reciprocal: drawing)
            }
            canvas.undoManager?.setActionName("Resize Selection")
            refreshSelectionBounds()
            onDrawingChanged(drawing)
            onUndoManagerChanged(canvas.undoManager)
        }

        /// Sets the viewport to exactly 100% logical scale while preserving valid zoom bounds and centering.
        func setZoomTo100Percent() {
            guard let scroll = scrollView else { return }
            if scroll.minimumZoomScale > 1.0 {
                scroll.minimumZoomScale = 0.05
            }
            if scroll.maximumZoomScale < 1.0 {
                scroll.maximumZoomScale = 10.0
            }
            scroll.setZoomScale(1.0, animated: false)
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            scroll.contentInset = .zero
            scroll.contentOffset = .zero
            selectionOverlay?.updateZoom(scroll.zoomScale)
            reportZoom()
        }

        /// Fits the logical canvas into the viewport and optionally resets pan/zoom for a new document or size.
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
            selectionOverlay?.updateZoom(scroll.zoomScale)
            reportZoom()
        }

        /// Centers a canvas that is smaller than the current viewport along either axis.
        func centerCanvas() {
            guard let scroll = scrollView else { return }
            let horizontal = max((scroll.bounds.width - scroll.contentSize.width) / 2, 0)
            let vertical = max((scroll.bounds.height - scroll.contentSize.height) / 2, 0)
            scroll.contentInset = UIEdgeInsets(top: vertical, left: horizontal, bottom: vertical, right: horizontal)
        }

        /// Sends the current absolute zoom scale to SwiftUI for the visible percentage readout.
        func reportZoom() {
            guard let scroll = scrollView else { return }
            onZoomChanged(scroll.zoomScale)
        }
    }
}
