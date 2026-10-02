import PencilKit
import UIKit

/// Lets a view host apply programmatic lasso previews without recording every drag sample as a new edit.
@MainActor
protocol LassoDrawingMutationHost: AnyObject {
    func applyLassoDrawing(_ drawing: PKDrawing, to canvas: PKCanvasView)
}

/// Selects, moves, and proportionally resizes one mixed raster + PencilKit selection.
@MainActor
final class RasterLassoInteractionController: NSObject, UIGestureRecognizerDelegate {
    private struct RasterFragment {
        let baseImage: UIImage
        let fragment: UIImage
        let originalBounds: CGRect
    }

    private struct Selection {
        let originalDrawing: PKDrawing
        let selectedStrokeIndices: [Int]
        let originalBounds: CGRect
        let raster: RasterFragment?
        var targetBounds: CGRect
    }

    private weak var canvas: PKCanvasView?
    private weak var backgroundView: UIImageView?
    private weak var hostView: UIView?
    private weak var historyController: CanvasEditHistoryController?
    private var overlay: RasterSelectionOverlayView?
    private weak var outsideSelectionTapRecognizer: UITapGestureRecognizer?
    private var selection: Selection?

    private var canvasSize = CGSize(width: 1240, height: 1754)
    private var canvasStateCommitted: ((PKDrawing, UIImage?, Bool) -> Void)?
    private var gestureStartBounds: CGRect?
    private var gestureStartPoint = CGPoint.zero

    func attach(canvas: PKCanvasView, backgroundView: UIImageView) {
        let host = canvas.superview ?? canvas
        if self.canvas === canvas, self.hostView === host {
            self.backgroundView = backgroundView
            resizeOverlay()
            return
        }

        if let recognizer = outsideSelectionTapRecognizer {
            recognizer.view?.removeGestureRecognizer(recognizer)
        }
        overlay?.removeFromSuperview()
        self.canvas = canvas
        self.backgroundView = backgroundView
        self.hostView = host

        let overlay = RasterSelectionOverlayView(frame: host.bounds)
        overlay.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        installGestures(on: overlay)
        host.addSubview(overlay)
        self.overlay = overlay
        installOutsideSelectionTap(on: host)
    }

    func bindRuntime(
        canvasSize: CGSize,
        historyController: CanvasEditHistoryController,
        canvasStateCommitted: @escaping (PKDrawing, UIImage?, Bool) -> Void
    ) {
        self.canvasSize = CGSize(
            width: max(canvasSize.width, 1),
            height: max(canvasSize.height, 1)
        )
        self.historyController = historyController
        self.canvasStateCommitted = canvasStateCommitted
        resizeOverlay()
    }

    func setEnabled(_ enabled: Bool) {
        overlay?.isUserInteractionEnabled = enabled
        if !enabled {
            clearSelection()
        }
    }

    func clearSelection() {
        selection = nil
        gestureStartBounds = nil
        overlay?.clearSelection()
    }

    /// Builds one selection from every enclosed layer instead of choosing raster OR strokes.
    func selectRasterRegion(with polygon: [CGPoint]) {
        guard polygon.count >= 3, let canvas else {
            clearSelection()
            return
        }

        let canvasRect = CGRect(origin: .zero, size: canvasSize)
        let path = closedPath(points: polygon)
        let lassoBounds = path.bounds.intersection(canvasRect).standardized
        guard !lassoBounds.isNull,
              lassoBounds.width > 1,
              lassoBounds.height > 1 else {
            clearSelection()
            return
        }

        let strokeIndices = selectedStrokeIndices(
            in: canvas.drawing,
            polygon: polygon
        )
        let strokeBounds = boundsOfSelectedStrokes(
            indices: strokeIndices,
            drawing: canvas.drawing
        )

        let raster = makeRasterFragment(
            path: path,
            bounds: lassoBounds
        )

        var combinedBounds = strokeBounds
        if let rasterBounds = raster?.originalBounds {
            combinedBounds = combinedBounds.map {
                $0.union(rasterBounds)
            } ?? rasterBounds
        }

        guard let bounds = combinedBounds?.intersection(canvasRect).standardized,
              !bounds.isNull,
              bounds.width > 1,
              bounds.height > 1 else {
            clearSelection()
            return
        }

        selection = Selection(
            originalDrawing: canvas.drawing,
            selectedStrokeIndices: strokeIndices,
            originalBounds: bounds,
            raster: raster,
            targetBounds: bounds
        )

        // Identity composition guarantees selection creation itself never duplicates content.
        applySelectionPreview()
    }

    private func installOutsideSelectionTap(on host: UIView) {
        let tap = UITapGestureRecognizer(
            target: self,
            action: #selector(handleOutsideSelectionTap(_:))
        )
        tap.allowedTouchTypes = [
            NSNumber(value: UITouch.TouchType.pencil.rawValue)
        ]
        tap.cancelsTouchesInView = false
        tap.delegate = self
        host.addGestureRecognizer(tap)
        outsideSelectionTapRecognizer = tap
    }

    @objc private func handleOutsideSelectionTap(
        _ recognizer: UITapGestureRecognizer
    ) {
        guard recognizer.state == .ended,
              selection != nil,
              let overlay else {
            return
        }
        let point = recognizer.location(in: overlay)
        guard !overlay.containsSelectionInteraction(at: point) else { return }
        clearSelection()
    }

    private func installGestures(on overlay: RasterSelectionOverlayView) {
        let bodyMove = UIPanGestureRecognizer(
            target: self,
            action: #selector(handleMove(_:))
        )
        bodyMove.maximumNumberOfTouches = 1
        bodyMove.allowedTouchTypes = [
            NSNumber(value: UITouch.TouchType.direct.rawValue),
            NSNumber(value: UITouch.TouchType.pencil.rawValue),
        ]
        bodyMove.delegate = self
        overlay.moveSurface.addGestureRecognizer(bodyMove)

        let handleMove = UIPanGestureRecognizer(
            target: self,
            action: #selector(handleMove(_:))
        )
        handleMove.maximumNumberOfTouches = 1
        handleMove.allowedTouchTypes = [
            NSNumber(value: UITouch.TouchType.direct.rawValue),
            NSNumber(value: UITouch.TouchType.pencil.rawValue),
        ]
        handleMove.delegate = self
        overlay.moveHandle.addGestureRecognizer(handleMove)

        for handle in overlay.handles {
            let resize = UIPanGestureRecognizer(
                target: self,
                action: #selector(handleResize(_:))
            )
            resize.maximumNumberOfTouches = 1
            resize.allowedTouchTypes = [
                NSNumber(value: UITouch.TouchType.direct.rawValue),
                NSNumber(value: UITouch.TouchType.pencil.rawValue),
            ]
            resize.delegate = self
            handle.addGestureRecognizer(resize)
        }
    }

    @objc private func handleMove(_ recognizer: UIPanGestureRecognizer) {
        guard selection != nil, let overlay else { return }
        let point = recognizer.location(in: overlay)

        switch recognizer.state {
        case .began:
            beginInteraction(startPoint: point)

        case .changed, .ended:
            guard let startBounds = gestureStartBounds else { return }
            let dx = point.x - gestureStartPoint.x
            let dy = point.y - gestureStartPoint.y
            var target = startBounds
            target.origin.x = min(
                max(startBounds.origin.x + dx, 0),
                max(canvasSize.width - target.width, 0)
            )
            target.origin.y = min(
                max(startBounds.origin.y + dy, 0),
                max(canvasSize.height - target.height, 0)
            )
            setTargetBounds(target)

            if recognizer.state == .ended {
                commitInteraction()
            }

        case .cancelled, .failed:
            cancelInteraction()

        default:
            break
        }
    }

    @objc private func handleResize(_ recognizer: UIPanGestureRecognizer) {
        guard selection != nil,
              let overlay,
              let view = recognizer.view,
              let corner = RasterSelectionOverlayView.Corner(
                rawValue: view.tag
              ) else {
            return
        }

        let point = recognizer.location(in: overlay)
        switch recognizer.state {
        case .began:
            beginInteraction(startPoint: point)

        case .changed, .ended:
            guard let original = gestureStartBounds else { return }
            setTargetBounds(
                resizedBounds(
                    original: original,
                    corner: corner,
                    currentPoint: point
                )
            )
            if recognizer.state == .ended {
                commitInteraction()
            }

        case .cancelled, .failed:
            cancelInteraction()

        default:
            break
        }
    }

    private func beginInteraction(startPoint: CGPoint) {
        guard let selection else { return }
        gestureStartBounds = selection.targetBounds
        gestureStartPoint = startPoint
        historyController?.beginGesture()
        canvas?.undoManager?.removeAllActions()
        setNavigationEnabled(false)
    }

    private func setTargetBounds(_ bounds: CGRect) {
        guard var selection else { return }
        selection.targetBounds = bounds.standardized
        self.selection = selection
        applySelectionPreview()
    }

    private func applySelectionPreview() {
        guard let selection,
              let canvas,
              let drawing = composedDrawing(for: selection) else {
            return
        }

        applyDrawing(drawing, to: canvas)
        if let image = composedBackground(for: selection) {
            backgroundView?.image = image
        }
        overlay?.setSelection(
            bounds: selection.targetBounds,
            zoomScale: outerScrollView()?.zoomScale ?? 1
        )
    }

    private func commitInteraction() {
        guard let selection,
              let canvas,
              let finalDrawing = composedDrawing(for: selection) else {
            finishInteraction()
            return
        }

        let finalImage = composedBackground(for: selection)
            ?? backgroundView?.image
        applyDrawing(finalDrawing, to: canvas)
        if let finalImage {
            backgroundView?.image = finalImage
        }

        let changed = historyController?.commitGesture(
            drawing: finalDrawing,
            backgroundImage: finalImage
        ) ?? true

        if changed {
            canvasStateCommitted?(
                finalDrawing,
                finalImage,
                selection.raster != nil
            )
        }

        canvas.undoManager?.removeAllActions()
        finishInteraction()
    }

    private func cancelInteraction() {
        if var selection, let startBounds = gestureStartBounds {
            selection.targetBounds = startBounds
            self.selection = selection
            applySelectionPreview()
        }
        _ = historyController?.cancelGesture()
        finishInteraction()
    }

    private func finishInteraction() {
        gestureStartBounds = nil
        setNavigationEnabled(true)
    }

    /// Replaces selected stroke indices in-place; selected strokes are never appended.
    private func composedDrawing(for selection: Selection) -> PKDrawing? {
        guard !selection.selectedStrokeIndices.isEmpty else {
            return selection.originalDrawing
        }

        let transform = geometryTransform(
            from: selection.originalBounds,
            to: selection.targetBounds
        )

        var allStrokes = selection.originalDrawing.strokes
        for index in selection.selectedStrokeIndices
        where index >= 0 && index < selection.originalDrawing.strokes.count {
            allStrokes[index] = strokeByApplyingGeometryTransform(
                selection.originalDrawing.strokes[index],
                transform: transform
            )
        }
        return PKDrawing(strokes: allStrokes)
    }

    private func composedBackground(for selection: Selection) -> UIImage? {
        guard let raster = selection.raster else {
            return backgroundView?.image
        }

        let transform = geometryTransform(
            from: selection.originalBounds,
            to: selection.targetBounds
        )
        let destination = raster.originalBounds
            .applying(transform)
            .standardized

        let format = UIGraphicsImageRendererFormat.default()
        format.scale = 1
        format.opaque = false
        return UIGraphicsImageRenderer(
            size: canvasSize,
            format: format
        ).image { _ in
            raster.baseImage.draw(
                in: CGRect(origin: .zero, size: canvasSize)
            )
            raster.fragment.draw(in: destination)
        }
    }

    private func geometryTransform(
        from original: CGRect,
        to target: CGRect
    ) -> CGAffineTransform {
        let safeWidth = max(original.width, 0.001)
        let safeHeight = max(original.height, 0.001)
        let scaleX = target.width / safeWidth
        let scaleY = target.height / safeHeight

        return CGAffineTransform(
            translationX: target.minX,
            y: target.minY
        )
        .scaledBy(x: scaleX, y: scaleY)
        .translatedBy(x: -original.minX, y: -original.minY)
    }

    private func applyDrawing(_ drawing: PKDrawing, to canvas: PKCanvasView) {
        if let host = canvas.delegate as? LassoDrawingMutationHost {
            host.applyLassoDrawing(drawing, to: canvas)
        } else {
            canvas.drawing = drawing
        }
    }

    private func makeRasterFragment(
        path: UIBezierPath,
        bounds: CGRect
    ) -> RasterFragment? {
        guard let image = backgroundView?.image,
              let normalized = RasterCanvasGeometry().normalizedImage(
                image,
                canvasSize: canvasSize
              ),
              let base = imageByClearing(path: path, from: normalized),
              let fragment = fragmentImage(
                path: path,
                bounds: bounds,
                source: normalized
              ) else {
            return nil
        }

        return RasterFragment(
            baseImage: base,
            fragment: fragment,
            originalBounds: bounds
        )
    }

    private func imageByClearing(
        path: UIBezierPath,
        from source: UIImage
    ) -> UIImage? {
        let format = UIGraphicsImageRendererFormat.default()
        format.scale = 1
        format.opaque = false
        return UIGraphicsImageRenderer(
            size: canvasSize,
            format: format
        ).image { rendererContext in
            source.draw(in: CGRect(origin: .zero, size: canvasSize))
            let context = rendererContext.cgContext
            context.saveGState()
            context.setBlendMode(.clear)
            context.addPath(path.cgPath)
            context.fillPath()
            context.restoreGState()
        }
    }

    private func fragmentImage(
        path: UIBezierPath,
        bounds: CGRect,
        source: UIImage
    ) -> UIImage? {
        let format = UIGraphicsImageRendererFormat.default()
        format.scale = 1
        format.opaque = false
        return UIGraphicsImageRenderer(
            size: bounds.size,
            format: format
        ).image { rendererContext in
            let context = rendererContext.cgContext
            context.saveGState()
            context.translateBy(x: -bounds.minX, y: -bounds.minY)
            context.addPath(path.cgPath)
            context.clip()
            source.draw(in: CGRect(origin: .zero, size: canvasSize))
            context.restoreGState()
        }
    }

    private func selectedStrokeIndices(
        in drawing: PKDrawing,
        polygon: [CGPoint]
    ) -> [Int] {
        drawing.strokes.enumerated().compactMap { index, stroke in
            strokeBelongsToSelection(stroke, polygon: polygon)
                ? index
                : nil
        }
    }

    /// Uses center, path coverage, and enclosed bounds so a lasso around a shape selects the whole shape.
    private func strokeBelongsToSelection(
        _ stroke: PKStroke,
        polygon: [CGPoint]
    ) -> Bool {
        let bounds = stroke.renderBounds.standardized
        let center = CGPoint(x: bounds.midX, y: bounds.midY)
        let centerInside = pointInPolygon(center, polygon: polygon)

        let corners = [
            CGPoint(x: bounds.minX, y: bounds.minY),
            CGPoint(x: bounds.maxX, y: bounds.minY),
            CGPoint(x: bounds.minX, y: bounds.maxY),
            CGPoint(x: bounds.maxX, y: bounds.maxY),
        ]
        let enclosedCorners = corners.reduce(into: 0) { count, point in
            if pointInPolygon(point, polygon: polygon) {
                count += 1
            }
        }

        let points = stroke.path.map {
            $0.location.applying(stroke.transform)
        }
        guard !points.isEmpty else {
            return centerInside || enclosedCorners >= 2
        }

        let insideCount = points.reduce(into: 0) { count, point in
            if pointInPolygon(point, polygon: polygon) {
                count += 1
            }
        }
        let fraction = CGFloat(insideCount) / CGFloat(points.count)

        return enclosedCorners >= 2
            || fraction >= 0.50
            || (centerInside && fraction >= 0.15)
    }

    private func boundsOfSelectedStrokes(
        indices: [Int],
        drawing: PKDrawing
    ) -> CGRect? {
        var result: CGRect?
        for index in indices
        where index >= 0 && index < drawing.strokes.count {
            let bounds = drawing.strokes[index].renderBounds.standardized
            result = result.map { $0.union(bounds) } ?? bounds
        }
        return result
    }

    /// Preserves visible stroke thickness while transforming only stroke geometry.
    private func strokeByApplyingGeometryTransform(
        _ stroke: PKStroke,
        transform: CGAffineTransform
    ) -> PKStroke {
        let points = stroke.path.map { point in
            PKStrokePoint(
                location: point.location
                    .applying(stroke.transform)
                    .applying(transform),
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

    private func closedPath(points: [CGPoint]) -> UIBezierPath {
        let path = UIBezierPath()
        path.move(to: points[0])
        for point in points.dropFirst() {
            path.addLine(to: point)
        }
        path.close()
        return path
    }

    private func resizedBounds(
        original: CGRect,
        corner: RasterSelectionOverlayView.Corner,
        currentPoint: CGPoint
    ) -> CGRect {
        let fixed = point(
            for: RasterSelectionOverlayView.opposite(corner),
            in: original
        )
        let rawWidth = abs(currentPoint.x - fixed.x)
        let rawHeight = abs(currentPoint.y - fixed.y)

        var scale = max(
            rawWidth / max(original.width, 0.001),
            rawHeight / max(original.height, 0.001)
        )
        let minimumScale = max(
            8 / max(original.width, 0.001),
            8 / max(original.height, 0.001)
        )
        scale = max(scale, minimumScale)

        let availableWidth: CGFloat
        let availableHeight: CGFloat
        switch corner {
        case .topLeft:
            availableWidth = fixed.x
            availableHeight = fixed.y
        case .topRight:
            availableWidth = canvasSize.width - fixed.x
            availableHeight = fixed.y
        case .bottomLeft:
            availableWidth = fixed.x
            availableHeight = canvasSize.height - fixed.y
        case .bottomRight:
            availableWidth = canvasSize.width - fixed.x
            availableHeight = canvasSize.height - fixed.y
        }

        let maximumScale = max(
            minimumScale,
            min(
                availableWidth / max(original.width, 0.001),
                availableHeight / max(original.height, 0.001)
            )
        )
        scale = min(scale, maximumScale)

        let size = CGSize(
            width: original.width * scale,
            height: original.height * scale
        )
        var frame = CGRect(origin: .zero, size: size)

        switch corner {
        case .topLeft:
            frame.origin = CGPoint(
                x: fixed.x - size.width,
                y: fixed.y - size.height
            )
        case .topRight:
            frame.origin = CGPoint(
                x: fixed.x,
                y: fixed.y - size.height
            )
        case .bottomLeft:
            frame.origin = CGPoint(
                x: fixed.x - size.width,
                y: fixed.y
            )
        case .bottomRight:
            frame.origin = fixed
        }
        return frame.standardized
    }

    private func point(
        for corner: RasterSelectionOverlayView.Corner,
        in frame: CGRect
    ) -> CGPoint {
        switch corner {
        case .topLeft:
            return CGPoint(x: frame.minX, y: frame.minY)
        case .topRight:
            return CGPoint(x: frame.maxX, y: frame.minY)
        case .bottomLeft:
            return CGPoint(x: frame.minX, y: frame.maxY)
        case .bottomRight:
            return CGPoint(x: frame.maxX, y: frame.maxY)
        }
    }

    private func pointInPolygon(
        _ point: CGPoint,
        polygon: [CGPoint]
    ) -> Bool {
        guard polygon.count >= 3 else { return false }

        var inside = false
        var previous = polygon.count - 1
        for current in 0..<polygon.count {
            let a = polygon[current]
            let b = polygon[previous]
            let denominator = b.y - a.y
            if (a.y > point.y) != (b.y > point.y),
               abs(denominator) > 0.000_001 {
                let intersectionX = (
                    (b.x - a.x) * (point.y - a.y) / denominator + a.x
                )
                if point.x < intersectionX {
                    inside.toggle()
                }
            }
            previous = current
        }
        return inside
    }

    private func resizeOverlay() {
        guard let hostView, let overlay else { return }
        overlay.frame = hostView.bounds
        overlay.updateZoom(outerScrollView()?.zoomScale ?? 1)
    }

    private func outerScrollView() -> UIScrollView? {
        var view = hostView?.superview
        while let current = view {
            if let scroll = current as? UIScrollView,
               scroll !== canvas {
                return scroll
            }
            view = current.superview
        }
        return nil
    }

    private func setNavigationEnabled(_ enabled: Bool) {
        outerScrollView()?.panGestureRecognizer.isEnabled = enabled
        outerScrollView()?.pinchGestureRecognizer?.isEnabled = enabled
    }
}
