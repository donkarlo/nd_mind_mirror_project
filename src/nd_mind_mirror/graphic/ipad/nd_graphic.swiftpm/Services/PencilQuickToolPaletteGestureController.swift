import UIKit

/// Uses the native iOS double-tap recognizer for Apple Pencil quick-tool activation.
final class PencilQuickToolPaletteGestureController: NSObject, UIGestureRecognizerDelegate {
    var onPencilContactBegan: (CGPoint) -> Void = { _ in }
    var onSinglePencilTap: (CGPoint) -> Void = { _ in }
    var onDoublePencilTap: (CGPoint) -> Void = { _ in }
    var onDoubleTapRejected: () -> Void = {}

    private weak var hostView: UIView?
    private weak var coordinateView: UIView?
    private weak var dismissTapGesture: UITapGestureRecognizer?
    private weak var doubleTapGesture: UITapGestureRecognizer?

    private let maximumInterTapInterval: TimeInterval = 0.35
    private let maximumInterTapDistance: CGFloat = 12

    private var palettePresented = false
    private var firstTapPoint: CGPoint?
    private var firstTapTimestamp: TimeInterval?
    private var secondTapPoint: CGPoint?
    private var secondTapTimestamp: TimeInterval?

    func attach(to view: UIView, coordinateView: UIView) {
        if hostView === view && self.coordinateView === coordinateView {
            return
        }
        detach()

        let doubleTap = UITapGestureRecognizer(
            target: self,
            action: #selector(handleDoubleTap(_:))
        )
        doubleTap.numberOfTapsRequired = 2
        doubleTap.numberOfTouchesRequired = 1
        doubleTap.allowedTouchTypes = [
            NSNumber(value: UITouch.TouchType.pencil.rawValue)
        ]
        doubleTap.cancelsTouchesInView = false
        doubleTap.delaysTouchesBegan = false
        doubleTap.delaysTouchesEnded = false
        doubleTap.delegate = self

        let dismissTap = UITapGestureRecognizer(
            target: self,
            action: #selector(handleDismissTap(_:))
        )
        dismissTap.numberOfTapsRequired = 1
        dismissTap.numberOfTouchesRequired = 1
        dismissTap.allowedTouchTypes = [
            NSNumber(value: UITouch.TouchType.pencil.rawValue)
        ]
        dismissTap.cancelsTouchesInView = false
        dismissTap.delaysTouchesBegan = false
        dismissTap.delaysTouchesEnded = false
        dismissTap.delegate = self
        dismissTap.isEnabled = false

        view.addGestureRecognizer(doubleTap)
        view.addGestureRecognizer(dismissTap)
        hostView = view
        self.coordinateView = coordinateView
        doubleTapGesture = doubleTap
        dismissTapGesture = dismissTap
    }

    func setPalettePresented(_ presented: Bool) {
        guard palettePresented != presented else {
            return
        }
        palettePresented = presented
        doubleTapGesture?.isEnabled = !presented
        dismissTapGesture?.isEnabled = presented
        clearTapSequence()
    }

    func detach() {
        if let dismissTapGesture {
            dismissTapGesture.view?.removeGestureRecognizer(dismissTapGesture)
        }
        if let doubleTapGesture {
            doubleTapGesture.view?.removeGestureRecognizer(doubleTapGesture)
        }
        dismissTapGesture = nil
        doubleTapGesture = nil
        hostView = nil
        coordinateView = nil
        palettePresented = false
        clearTapSequence()
    }

    @objc private func handleDoubleTap(_ gesture: UITapGestureRecognizer) {
        guard gesture.state == .ended,
              let firstTapPoint,
              let firstTapTimestamp,
              let secondTapPoint,
              let secondTapTimestamp else {
            onDoubleTapRejected()
            clearTapSequence()
            return
        }

        let elapsed = secondTapTimestamp - firstTapTimestamp
        let valid =
            elapsed <= maximumInterTapInterval
            && distance(from: firstTapPoint, to: secondTapPoint)
                <= maximumInterTapDistance

        clearTapSequence()

        guard valid else {
            onDoubleTapRejected()
            return
        }
        onDoublePencilTap(secondTapPoint)
    }

    @objc private func handleDismissTap(_ gesture: UITapGestureRecognizer) {
        guard gesture.state == .ended,
              palettePresented,
              let coordinateView else {
            return
        }
        clearTapSequence()
        onSinglePencilTap(viewportPoint(
            for: gesture.location(in: coordinateView),
            in: coordinateView
        ))
    }

    func gestureRecognizer(
        _ gestureRecognizer: UIGestureRecognizer,
        shouldReceive touch: UITouch
    ) -> Bool {
        guard touch.type == .pencil else {
            return false
        }

        if gestureRecognizer === doubleTapGesture,
           let coordinateView {
            let point = viewportPoint(
                for: touch.location(in: coordinateView),
                in: coordinateView
            )
            if touch.tapCount <= 1 {
                firstTapPoint = point
                firstTapTimestamp = ProcessInfo.processInfo.systemUptime
                secondTapPoint = nil
                secondTapTimestamp = nil
                onPencilContactBegan(point)
            } else {
                secondTapPoint = point
                secondTapTimestamp = ProcessInfo.processInfo.systemUptime
            }
        } else if gestureRecognizer === dismissTapGesture,
                  let coordinateView {
            onPencilContactBegan(viewportPoint(
                for: touch.location(in: coordinateView),
                in: coordinateView
            ))
        }
        return true
    }

    func gestureRecognizer(
        _ gestureRecognizer: UIGestureRecognizer,
        shouldRecognizeSimultaneouslyWith otherGestureRecognizer: UIGestureRecognizer
    ) -> Bool {
        true
    }

    /// UIKit reports touch locations in the scroll view's scrolled bounds.
    /// SwiftUI overlays use the visible viewport, whose origin is (0, 0).
    /// Subtracting bounds.origin handles centering insets, panning, and zoom.
    private func viewportPoint(
        for location: CGPoint,
        in coordinateView: UIView
    ) -> CGPoint {
        CGPoint(
            x: location.x - coordinateView.bounds.minX,
            y: location.y - coordinateView.bounds.minY
        )
    }

    private func clearTapSequence() {
        firstTapPoint = nil
        firstTapTimestamp = nil
        secondTapPoint = nil
        secondTapTimestamp = nil
    }

    private func distance(from lhs: CGPoint, to rhs: CGPoint) -> CGFloat {
        hypot(lhs.x - rhs.x, lhs.y - rhs.y)
    }
}
