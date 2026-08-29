import UIKit
import UIKit.UIGestureRecognizerSubclass

/// Recognizes Apple Pencil movement immediately and preserves coalesced samples.
/// It lives on the canvas container so PencilKit can receive the same Pencil stream.
final class PencilRasterEraserGestureRecognizer: UIGestureRecognizer {
    private(set) var currentPoints: [CGPoint] = []

    override init(target: Any?, action: Selector?) {
        super.init(target: target, action: action)
        configureForPencil()
    }

    required init?(coder: NSCoder) {
        fatalError("PencilRasterEraserGestureRecognizer does not support NSCoder initialization.")
    }

    override func touchesBegan(_ touches: Set<UITouch>, with event: UIEvent) {
        let points = pencilPoints(from: touches, event: event)
        guard !points.isEmpty else {
            state = .failed
            return
        }
        currentPoints = points
        state = .began
    }

    override func touchesMoved(_ touches: Set<UITouch>, with event: UIEvent) {
        let points = pencilPoints(from: touches, event: event)
        guard !points.isEmpty else { return }
        currentPoints = points
        state = .changed
    }

    override func touchesEnded(_ touches: Set<UITouch>, with event: UIEvent) {
        let points = pencilPoints(from: touches, event: event)
        if !points.isEmpty {
            currentPoints = points
        }
        if state == .began || state == .changed {
            state = .ended
        } else {
            state = .failed
        }
    }

    override func touchesCancelled(_ touches: Set<UITouch>, with event: UIEvent) {
        currentPoints = []
        state = .cancelled
    }

    override func reset() {
        currentPoints = []
        super.reset()
    }

    private func configureForPencil() {
        allowedTouchTypes = [NSNumber(value: UITouch.TouchType.pencil.rawValue)]
        cancelsTouchesInView = false
        delaysTouchesBegan = false
        delaysTouchesEnded = false
    }

    private func pencilPoints(from touches: Set<UITouch>, event: UIEvent) -> [CGPoint] {
        guard let view else { return [] }
        var result: [CGPoint] = []
        for touch in touches where touch.type == .pencil {
            let samples = event.coalescedTouches(for: touch) ?? [touch]
            for sample in samples where sample.type == .pencil {
                let point = sample.location(in: view)
                if result.last != point {
                    result.append(point)
                }
            }
        }
        return result
    }
}
