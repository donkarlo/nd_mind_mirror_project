// Coalesces rapid PencilKit drawing callbacks while preserving a true live Ubuntu update stream.

import Combine
import Foundation

@MainActor
final class LiveGraphicSaveScheduler: ObservableObject {
    private var pendingWorkItem: DispatchWorkItem?
    private var latestAction: (() -> Void)?
    private var lastSentUptime = -Double.greatestFiniteMagnitude

    func submit(updateRateHz: Double, action: @escaping () -> Void) {
        latestAction = action

        let rate = max(updateRateHz, 1.0)
        let interval = 1.0 / rate
        let now = ProcessInfo.processInfo.systemUptime
        let elapsed = now - lastSentUptime

        if elapsed >= interval {
            sendLatest()
            return
        }

        guard pendingWorkItem == nil else { return }
        let delay = max(interval - elapsed, 0)
        let workItem = DispatchWorkItem { [weak self] in
            Task { @MainActor in
                self?.sendLatest()
            }
        }
        pendingWorkItem = workItem
        DispatchQueue.main.asyncAfter(deadline: .now() + delay, execute: workItem)
    }

    func cancelPending() {
        pendingWorkItem?.cancel()
        pendingWorkItem = nil
        latestAction = nil
    }

    func flush() {
        pendingWorkItem?.cancel()
        pendingWorkItem = nil
        sendLatest()
    }

    private func sendLatest() {
        pendingWorkItem?.cancel()
        pendingWorkItem = nil
        guard let action = latestAction else { return }
        latestAction = nil
        lastSentUptime = ProcessInfo.processInfo.systemUptime
        action()
    }
}
