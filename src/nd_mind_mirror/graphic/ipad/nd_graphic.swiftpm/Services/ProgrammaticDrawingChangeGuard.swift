import Foundation
import PencilKit
import SwiftUI

/// Remembers recent programmatic PencilKit states so delayed delegate callbacks cannot become new edits.
@MainActor
final class ProgrammaticDrawingChangeGuard: ObservableObject {
    private let lifetime: TimeInterval
    private let maximumCount: Int
    private var expectedStates: [(data: Data, expiresAt: Date)] = []

    init(lifetime: TimeInterval = 2.0, maximumCount: Int = 64) {
        self.lifetime = max(lifetime, 0.1)
        self.maximumCount = max(maximumCount, 4)
    }

    func reset() {
        expectedStates.removeAll(keepingCapacity: false)
    }

    func register(_ drawing: PKDrawing) {
        pruneExpired()
        let data = drawing.dataRepresentation()
        expectedStates.removeAll { $0.data == data }
        expectedStates.append(
            (data: data, expiresAt: Date().addingTimeInterval(lifetime))
        )
        let overflow = expectedStates.count - maximumCount
        if overflow > 0 {
            expectedStates.removeFirst(overflow)
        }
    }

    func matches(_ drawing: PKDrawing) -> Bool {
        pruneExpired()
        let data = drawing.dataRepresentation()
        return expectedStates.contains { $0.data == data }
    }

    private func pruneExpired() {
        let now = Date()
        expectedStates.removeAll { $0.expiresAt <= now }
    }
}
