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
        onSinglePencilTap(gesture.location(in: coordinateView))
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
            if touch.tapCount <= 1 {
                firstTapPoint = touch.location(in: coordinateView)
                firstTapTimestamp = ProcessInfo.processInfo.systemUptime
                secondTapPoint = nil
                secondTapTimestamp = nil
                onPencilContactBegan(firstTapPoint ?? touch.location(in: coordinateView))
            } else {
                secondTapPoint = touch.location(in: coordinateView)
                secondTapTimestamp = ProcessInfo.processInfo.systemUptime
            }
        } else if gestureRecognizer === dismissTapGesture,
                  let coordinateView {
            onPencilContactBegan(touch.location(in: coordinateView))
        }
        return true
    }

    func gestureRecognizer(
        _ gestureRecognizer: UIGestureRecognizer,
        shouldRecognizeSimultaneouslyWith otherGestureRecognizer: UIGestureRecognizer
    ) -> Bool {
        true
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
