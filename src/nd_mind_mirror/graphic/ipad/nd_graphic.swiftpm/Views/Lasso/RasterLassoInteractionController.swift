import PencilKit
import UIKit

/// Selects, moves, and proportionally resizes arbitrary pixels from the raster background.
@MainActor
final class RasterLassoInteractionController: NSObject, UIGestureRecognizerDelegate {
    private struct Selection {
        let baseImage: UIImage
        let fragment: UIImage
        var targetBounds: CGRect
    }

    private weak var canvas: PKCanvasView?
    private weak var backgroundView: UIImageView?
    private weak var hostView: UIView?
    private weak var historyController: CanvasEditHistoryController?
    private var overlay: RasterSelectionOverlayView?
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

        overlay?.removeFromSuperview()
        self.canvas = canvas
        self.backgroundView = backgroundView
        self.hostView = host

        let overlay = RasterSelectionOverlayView(frame: host.bounds)
        overlay.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        installGestures(on: overlay)
        host.addSubview(overlay)
        self.overlay = overlay
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

    func selectRasterRegion(with polygon: [CGPoint]) {
        guard polygon.count >= 3,
              let canvas,
              let image = backgroundView?.image,
              !containsSelectableStroke(in: canvas.drawing, polygon: polygon),
              let normalized = RasterCanvasGeometry().normalizedImage(
                image,
                canvasSize: canvasSize
              ) else {
            return
        }

        let canvasRect = CGRect(origin: .zero, size: canvasSize)
        let path = closedPath(points: polygon)
        let selectedBounds = path.bounds.intersection(canvasRect).standardized
        guard !selectedBounds.isNull,
              selectedBounds.width > 1,
              selectedBounds.height > 1,
              let base = imageByClearing(path: path, from: normalized),
              let fragment = fragmentImage(
                path: path,
                bounds: selectedBounds,
                source: normalized
              ) else {
            clearSelection()
            return
        }

        selection = Selection(
            baseImage: base,
            fragment: fragment,
            targetBounds: selectedBounds
        )
        backgroundView?.image = composeCurrentSelection()
        overlay?.setSelection(
            bounds: selectedBounds,
            zoomScale: outerScrollView()?.zoomScale ?? 1
        )
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
        guard var selection, let overlay else { return }
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
            selection.targetBounds = target
            self.selection = selection
            refreshPreview()
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
        guard var selection,
              let overlay,
              let view = recognizer.view,
              let corner = RasterSelectionOverlayView.Corner(rawValue: view.tag),
              let startBounds = gestureStartBounds ?? overlay.selectionBounds else {
            return
        }

        let point = recognizer.location(in: overlay)
        switch recognizer.state {
        case .began:
            beginInteraction(startPoint: point)

        case .changed, .ended:
            guard let original = gestureStartBounds else { return }
            selection.targetBounds = resizedBounds(
                original: original,
                corner: corner,
                currentPoint: point
            )
            self.selection = selection
            refreshPreview()
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

    private func commitInteraction() {
        guard let canvas,
              let finalImage = composeCurrentSelection() else {
            finishInteraction()
            return
        }

        backgroundView?.image = finalImage
        let changed = historyController?.commitGesture(
            drawing: canvas.drawing,
            backgroundImage: finalImage
        ) ?? true
        if changed {
            canvasStateCommitted?(canvas.drawing, finalImage, true)
        }
        canvas.undoManager?.removeAllActions()
        finishInteraction()
    }

    private func cancelInteraction() {
        if var selection, let startBounds = gestureStartBounds {
            selection.targetBounds = startBounds
            self.selection = selection
            refreshPreview()
        }
        _ = historyController?.cancelGesture()
        finishInteraction()
    }

    private func finishInteraction() {
        gestureStartBounds = nil
        setNavigationEnabled(true)
    }

    private func refreshPreview() {
        guard let selection,
              let image = composeCurrentSelection() else { return }
        backgroundView?.image = image
        overlay?.setSelection(
            bounds: selection.targetBounds,
            zoomScale: outerScrollView()?.zoomScale ?? 1
        )
    }

    private func composeCurrentSelection() -> UIImage? {
        guard let selection else { return backgroundView?.image }
        let format = UIGraphicsImageRendererFormat.default()
        format.scale = 1
        format.opaque = false
        return UIGraphicsImageRenderer(size: canvasSize, format: format).image { _ in
            selection.baseImage.draw(in: CGRect(origin: .zero, size: canvasSize))
            selection.fragment.draw(in: selection.targetBounds)
        }
    }

    private func imageByClearing(path: UIBezierPath, from source: UIImage) -> UIImage? {
        let format = UIGraphicsImageRendererFormat.default()
        format.scale = 1
        format.opaque = false
        return UIGraphicsImageRenderer(size: canvasSize, format: format).image { rendererContext in
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
        return UIGraphicsImageRenderer(size: bounds.size, format: format).image { rendererContext in
            let context = rendererContext.cgContext
            context.saveGState()
            context.translateBy(x: -bounds.minX, y: -bounds.minY)
            context.addPath(path.cgPath)
            context.clip()
            source.draw(in: CGRect(origin: .zero, size: canvasSize))
            context.restoreGState()
        }
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
            frame.origin = CGPoint(x: fixed.x - size.width, y: fixed.y - size.height)
        case .topRight:
            frame.origin = CGPoint(x: fixed.x, y: fixed.y - size.height)
        case .bottomLeft:
            frame.origin = CGPoint(x: fixed.x - size.width, y: fixed.y)
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
        case .topLeft: return CGPoint(x: frame.minX, y: frame.minY)
        case .topRight: return CGPoint(x: frame.maxX, y: frame.minY)
        case .bottomLeft: return CGPoint(x: frame.minX, y: frame.maxY)
        case .bottomRight: return CGPoint(x: frame.maxX, y: frame.maxY)
        }
    }

    private func containsSelectableStroke(
        in drawing: PKDrawing,
        polygon: [CGPoint]
    ) -> Bool {
        for stroke in drawing.strokes {
            let center = CGPoint(
                x: stroke.renderBounds.midX,
                y: stroke.renderBounds.midY
            )
            let points = stroke.path.map {
                $0.location.applying(stroke.transform)
            }
            if points.isEmpty {
                if pointInPolygon(center, polygon: polygon) { return true }
                continue
            }

            let insideCount = points.reduce(into: 0) { count, point in
                if pointInPolygon(point, polygon: polygon) { count += 1 }
            }
            let fraction = CGFloat(insideCount) / CGFloat(points.count)
            if fraction >= 0.55
                || (pointInPolygon(center, polygon: polygon) && fraction >= 0.25) {
                return true
            }
        }
        return false
    }

    private func pointInPolygon(_ point: CGPoint, polygon: [CGPoint]) -> Bool {
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
