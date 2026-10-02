import Foundation
import SwiftUI

/// Tracks the sequence of graphics opened during the current iPad app session.
@MainActor
final class GraphicDocumentNavigationHistory: ObservableObject {
    @Published private(set) var canGoBack = false
    @Published private(set) var canGoForward = false

    private var paths: [String] = []
    private var currentIndex: Int?
    private var requestedIndex: Int?

    func recordOpened(path: String) {
        guard !path.isEmpty else { return }

        if let requestedIndex,
           paths.indices.contains(requestedIndex),
           paths[requestedIndex] == path {
            currentIndex = requestedIndex
            self.requestedIndex = nil
            publishAvailability()
            return
        }

        requestedIndex = nil
        if let currentIndex, paths[currentIndex] == path {
            publishAvailability()
            return
        }

        if let currentIndex, currentIndex + 1 < paths.count {
            paths.removeSubrange((currentIndex + 1)..<paths.count)
        }
        paths.append(path)
        currentIndex = paths.count - 1
        publishAvailability()
    }

    func remapPath(from oldPath: String, to newPath: String) {
        guard !oldPath.isEmpty, !newPath.isEmpty, oldPath != newPath else { return }
        for index in paths.indices where paths[index] == oldPath {
            paths[index] = newPath
        }
        publishAvailability()
    }

    func cancelPendingNavigation() {
        requestedIndex = nil
        publishAvailability()
    }

    func backPath() -> String? {
        requestPath(offset: -1)
    }

    func forwardPath() -> String? {
        requestPath(offset: 1)
    }

    private func requestPath(offset: Int) -> String? {
        guard requestedIndex == nil, let currentIndex else { return nil }
        let target = currentIndex + offset
        guard paths.indices.contains(target) else { return nil }
        requestedIndex = target
        publishAvailability()
        return paths[target]
    }

    private func publishAvailability() {
        guard requestedIndex == nil, let currentIndex else {
            canGoBack = false
            canGoForward = false
            return
        }
        canGoBack = currentIndex > 0
        canGoForward = currentIndex + 1 < paths.count
    }
}
