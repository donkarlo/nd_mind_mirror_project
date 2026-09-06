import Combine
import PencilKit
import UIKit

/// Blocks persistence until a remote graphic has been fully hydrated on the iPad.
@MainActor
final class GraphicDocumentSaveGate: ObservableObject {
    private enum State: Equatable {
        case empty
        case loading(path: String)
        case ready(path: String)
        case blocked(path: String)
    }

    private var state: State = .empty

    func beginLoading(path: String) {
        state = .loading(path: path)
    }

    func finishLoading(
        path: String,
        operation: String,
        drawing: PKDrawing,
        backgroundImage: UIImage?,
        hasImageObjects: Bool
    ) {
        guard state == .loading(path: path) else { return }

        let hasHydratedContent =
            operation == "insert"
            || backgroundImage != nil
            || !drawing.strokes.isEmpty
            || hasImageObjects

        state = hasHydratedContent ? .ready(path: path) : .blocked(path: path)
    }

    /// Preserve hydration state when Ubuntu renames the currently open graphic.
    func remapPath(from oldPath: String, to newPath: String) {
        guard oldPath != newPath else { return }
        switch state {
        case .loading(let path) where path == oldPath:
            state = .loading(path: newPath)
        case .ready(let path) where path == oldPath:
            state = .ready(path: newPath)
        case .blocked(let path) where path == oldPath:
            state = .blocked(path: newPath)
        default:
            break
        }
    }

    func reset() {
        state = .empty
    }

    func allowsSave(path: String?) -> Bool {
        guard let path else { return false }
        return state == .ready(path: path)
    }
}
