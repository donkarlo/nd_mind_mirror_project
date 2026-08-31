import PencilKit
import SwiftUI
import UIKit

/// Stores complete canvas states so drawing strokes and raster pixels always undo together.
@MainActor
final class CanvasEditHistoryController: ObservableObject {
    struct Snapshot {
        let drawing: PKDrawing
        let backgroundImage: UIImage?
    }

    @Published private(set) var canUndo = false
    @Published private(set) var canRedo = false

    private let maximumDepth: Int
    private var undoStack: [Snapshot] = []
    private var redoStack: [Snapshot] = []
    private var currentSnapshot: Snapshot?
    private var gestureStartSnapshot: Snapshot?

    init(maximumDepth: Int = 200) {
        self.maximumDepth = max(1, maximumDepth)
    }

    func reset(drawing: PKDrawing, backgroundImage: UIImage?) {
        undoStack.removeAll(keepingCapacity: false)
        redoStack.removeAll(keepingCapacity: false)
        currentSnapshot = Snapshot(drawing: drawing, backgroundImage: backgroundImage)
        gestureStartSnapshot = nil
        refreshAvailability()
    }

    func beginGesture() {
        guard gestureStartSnapshot == nil else { return }
        gestureStartSnapshot = currentSnapshot
    }

    @discardableResult
    func commitGesture(drawing: PKDrawing, backgroundImage: UIImage?) -> Bool {
        let previous = gestureStartSnapshot ?? currentSnapshot
        gestureStartSnapshot = nil
        return commit(
            previous: previous,
            next: Snapshot(drawing: drawing, backgroundImage: backgroundImage)
        )
    }

    @discardableResult
    func record(drawing: PKDrawing, backgroundImage: UIImage?) -> Bool {
        gestureStartSnapshot = nil
        return commit(
            previous: currentSnapshot,
            next: Snapshot(drawing: drawing, backgroundImage: backgroundImage)
        )
    }

    func cancelGesture() -> Snapshot? {
        gestureStartSnapshot = nil
        return currentSnapshot
    }

    func undo() -> Snapshot? {
        gestureStartSnapshot = nil
        guard let currentSnapshot, let previous = undoStack.popLast() else {
            refreshAvailability()
            return nil
        }
        redoStack.append(currentSnapshot)
        trim(&redoStack)
        self.currentSnapshot = previous
        refreshAvailability()
        return previous
    }

    func redo() -> Snapshot? {
        gestureStartSnapshot = nil
        guard let currentSnapshot, let next = redoStack.popLast() else {
            refreshAvailability()
            return nil
        }
        undoStack.append(currentSnapshot)
        trim(&undoStack)
        self.currentSnapshot = next
        refreshAvailability()
        return next
    }

    private func commit(previous: Snapshot?, next: Snapshot) -> Bool {
        if let previous, snapshotsAreEquivalent(previous, next) {
            currentSnapshot = next
            refreshAvailability()
            return false
        }

        if let previous {
            undoStack.append(previous)
            trim(&undoStack)
        }
        redoStack.removeAll(keepingCapacity: false)
        currentSnapshot = next
        refreshAvailability()
        return true
    }

    private func snapshotsAreEquivalent(_ lhs: Snapshot, _ rhs: Snapshot) -> Bool {
        guard lhs.drawing.dataRepresentation() == rhs.drawing.dataRepresentation() else {
            return false
        }
        return imagesAreEquivalent(lhs.backgroundImage, rhs.backgroundImage)
    }

    private func imagesAreEquivalent(_ lhs: UIImage?, _ rhs: UIImage?) -> Bool {
        if lhs === rhs { return true }
        switch (lhs, rhs) {
        case (nil, nil):
            return true
        case let (left?, right?):
            return left.pngData() == right.pngData()
        default:
            return false
        }
    }

    private func trim(_ stack: inout [Snapshot]) {
        let overflow = stack.count - maximumDepth
        if overflow > 0 {
            stack.removeFirst(overflow)
        }
    }

    private func refreshAvailability() {
        canUndo = !undoStack.isEmpty
        canRedo = !redoStack.isEmpty
    }
}
