import Combine
import Foundation

/// Decides whether the active-tool icon may appear after Pencil inactivity.
@MainActor
final class PencilContactPreviewVisibilityController: ObservableObject {
    private var lastDrawingActivityUptime: TimeInterval?

    func recordDrawingActivity() {
        lastDrawingActivityUptime = ProcessInfo.processInfo.systemUptime
    }

    func shouldShow(minimumIdleSeconds: Double) -> Bool {
        guard let lastDrawingActivityUptime else {
            return true
        }
        let idleTime = ProcessInfo.processInfo.systemUptime - lastDrawingActivityUptime
        return idleTime >= minimumIdleSeconds
    }

    func reset() {
        lastDrawingActivityUptime = nil
    }
}
