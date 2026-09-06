// Draws the visual path for the custom Pencil lasso without re-enabling PKLassoTool.

import PencilKit
import UIKit

/// Mirrors PencilKit's gray dashed lasso feedback while the app keeps ownership of selection geometry.
@MainActor
final class LassoSelectionFeedbackController: NSObject, UIGestureRecognizerDelegate {
    var onLassoCompleted: (([CGPoint]) -> Void)?

    private weak var canvas: PKCanvasView?
    private weak var hostView: UIView?
    private weak var selectionOverlay: SelectionResizeOverlay?

    private let pathLayer = CAShapeLayer()
    private var pencilRecognizer: UIPanGestureRecognizer?
    private var displayLink: CADisplayLink?

    private var freehandPoints: [CGPoint] = []
    private var completedPoints: [CGPoint] = []
    private var referenceSelectionBounds: CGRect?
    private var trackingFreehand = false
    private var waitingForSelectionUntil: CFTimeInterval = 0
    private var enabled = false

    override init() {
        super.init()
        pathLayer.fillColor = UIColor.clear.cgColor
        pathLayer.strokeColor = UIColor.systemGray.cgColor
        pathLayer.lineCap = .round
        pathLayer.lineJoin = .round
        pathLayer.isHidden = true
    }

    deinit {
        displayLink?.invalidate()
    }

    func attach(to canvas: PKCanvasView) {
        if self.canvas === canvas {
            resolveSelectionOverlay()
            return
        }

        detach()
        self.canvas = canvas

        let host = canvas.superview ?? canvas
        hostView = host
        pathLayer.frame = host.bounds
        resolveSelectionOverlay()
        installPathLayer(in: host)

        let recognizer = UIPanGestureRecognizer(
            target: self,
            action: #selector(handlePencilLasso(_:))
        )
        recognizer.allowedTouchTypes = [
            NSNumber(value: UITouch.TouchType.pencil.rawValue)
        ]
        recognizer.maximumNumberOfTouches = 1
        recognizer.cancelsTouchesInView = false
        recognizer.delegate = self
        canvas.addGestureRecognizer(recognizer)
        pencilRecognizer = recognizer

        let displayLink = CADisplayLink(
            target: self,
            selector: #selector(refreshPersistentPath)
        )
        displayLink.add(to: .main, forMode: .common)
        displayLink.isPaused = !enabled
        self.displayLink = displayLink

        recognizer.isEnabled = enabled
    }

    func detach() {
        if let recognizer = pencilRecognizer {
            recognizer.view?.removeGestureRecognizer(recognizer)
        }
        pencilRecognizer = nil
        displayLink?.invalidate()
        displayLink = nil
        pathLayer.removeFromSuperlayer()
        canvas = nil
        hostView = nil
        selectionOverlay = nil
        clearPath()
    }

    func setEnabled(_ enabled: Bool) {
        self.enabled = enabled
        pencilRecognizer?.isEnabled = enabled
        displayLink?.isPaused = !enabled
        if !enabled {
            clearPath()
        }
    }

    func gestureRecognizer(
        _ gestureRecognizer: UIGestureRecognizer,
        shouldRecognizeSimultaneouslyWith otherGestureRecognizer: UIGestureRecognizer
    ) -> Bool {
        true
    }

    @objc private func handlePencilLasso(_ recognizer: UIPanGestureRecognizer) {
        guard enabled, let hostView else { return }

        switch recognizer.state {
        case .began:
            resolveSelectionOverlay()
            trackingFreehand = true
            referenceSelectionBounds = nil
            completedPoints.removeAll(keepingCapacity: true)
            freehandPoints = [recognizer.location(in: hostView)]
            waitingForSelectionUntil = 0
            render(points: freehandPoints, closed: false)

        case .changed:
            let point = recognizer.location(in: hostView)
            if let previous = freehandPoints.last {
                let dx = point.x - previous.x
                let dy = point.y - previous.y
                if dx * dx + dy * dy < 4.0 {
                    return
                }
            }
            freehandPoints.append(point)
            render(points: freehandPoints, closed: false)

        case .ended:
            freehandPoints.append(recognizer.location(in: hostView))
            completedPoints = freehandPoints
            trackingFreehand = false
            waitingForSelectionUntil = CACurrentMediaTime() + 0.20
            render(points: completedPoints, closed: true)
            onLassoCompleted?(completedPoints)
            DispatchQueue.main.async { [weak self] in
                self?.refreshPersistentPath()
            }

        case .cancelled, .failed:
            clearPath()

        default:
            break
        }
    }

    @objc private func refreshPersistentPath() {
        guard enabled, !trackingFreehand else { return }
        guard let hostView else {
            clearPath()
            return
        }

        pathLayer.frame = hostView.bounds
        resolveSelectionOverlay()

        guard let overlay = selectionOverlay,
              !overlay.isHidden,
              let currentBounds = selectionBounds(from: overlay) else {
            if CACurrentMediaTime() >= waitingForSelectionUntil {
                clearPath()
            }
            return
        }

        waitingForSelectionUntil = 0
        guard !completedPoints.isEmpty else { return }

        if referenceSelectionBounds == nil {
            referenceSelectionBounds = currentBounds
            render(points: completedPoints, closed: true)
            return
        }

        guard let reference = referenceSelectionBounds else { return }
        let transformed = transformedPoints(
            completedPoints,
            from: reference,
            to: currentBounds
        )
        render(points: transformed, closed: true)
    }

    private func installPathLayer(in host: UIView) {
        if let overlay = selectionOverlay,
           overlay.superview === host {
            host.layer.insertSublayer(pathLayer, below: overlay.layer)
        } else {
            host.layer.addSublayer(pathLayer)
        }
    }

    private func resolveSelectionOverlay() {
        guard let hostView else {
            selectionOverlay = nil
            return
        }
        selectionOverlay = hostView.subviews
            .compactMap { $0 as? SelectionResizeOverlay }
            .last
    }

    private func selectionBounds(from overlay: SelectionResizeOverlay) -> CGRect? {
        let centers = overlay.handles.map(\.center)
        guard centers.count == 4 else { return nil }
        let minimumX = centers.map(\.x).min() ?? 0
        let maximumX = centers.map(\.x).max() ?? 0
        let minimumY = centers.map(\.y).min() ?? 0
        let maximumY = centers.map(\.y).max() ?? 0
        let bounds = CGRect(
            x: minimumX,
            y: minimumY,
            width: maximumX - minimumX,
            height: maximumY - minimumY
        )
        guard bounds.width > 0.5, bounds.height > 0.5 else { return nil }
        return bounds
    }

    private func transformedPoints(
        _ points: [CGPoint],
        from reference: CGRect,
        to current: CGRect
    ) -> [CGPoint] {
        let referenceWidth = max(reference.width, 0.001)
        let referenceHeight = max(reference.height, 0.001)
        let scaleX = current.width / referenceWidth
        let scaleY = current.height / referenceHeight

        return points.map { point in
            CGPoint(
                x: current.minX + (point.x - reference.minX) * scaleX,
                y: current.minY + (point.y - reference.minY) * scaleY
            )
        }
    }

    private func render(points: [CGPoint], closed: Bool) {
        guard !points.isEmpty else {
            pathLayer.path = nil
            pathLayer.isHidden = true
            return
        }

        updateStrokeMetrics()
        let path = UIBezierPath()
        path.move(to: points[0])
        for point in points.dropFirst() {
            path.addLine(to: point)
        }
        if closed, points.count >= 3 {
            path.close()
        }
        pathLayer.path = path.cgPath
        pathLayer.isHidden = false
    }

    private func updateStrokeMetrics() {
        let zoomScale = outerScrollView()?.zoomScale ?? 1.0
        let scale = max(zoomScale, 0.05)
        pathLayer.lineWidth = max(1.35 / scale, 0.45)
        pathLayer.lineDashPattern = [
            NSNumber(value: Double(3.0 / scale)),
            NSNumber(value: Double(4.0 / scale))
        ]
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

    private func clearPath() {
        freehandPoints.removeAll(keepingCapacity: false)
        completedPoints.removeAll(keepingCapacity: false)
        referenceSelectionBounds = nil
        trackingFreehand = false
        waitingForSelectionUntil = 0
        pathLayer.path = nil
        pathLayer.isHidden = true
    }
}
