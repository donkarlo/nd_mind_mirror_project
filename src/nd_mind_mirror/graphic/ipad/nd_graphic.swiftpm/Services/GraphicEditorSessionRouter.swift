// Routes one shared Mind Mirror bridge session to the correct iPad editor.

import Foundation
import SwiftUI
import UIKit

@MainActor
final class GraphicEditorSessionRouter: ObservableObject {
    enum Workspace {
        case image
        case tikz
    }

    static let shared = GraphicEditorSessionRouter()

    @Published private(set) var workspace: Workspace = .image
    @Published private(set) var tikzPath: String?
    @Published private(set) var tikzSource = ""
    @Published private(set) var tikzPreviewImage: UIImage?
    @Published private(set) var tikzStatus = ""

    private var sendCommand: (([String: Any]) -> Void)?
    private var nextRevision = 1
    private var latestRevision = 0
    @Published private(set) var canUndoTikZ = false
    @Published private(set) var canRedoTikZ = false
    private var undoTikZSources: [String] = []
    private var redoTikZSources: [String] = []
    private var previousHistoryGroup: String?
    private var lastGroupedEditAt = -Double.greatestFiniteMagnitude
    private let maximumHistoryDepth = 200
    private let tikzSourceSyncScheduler = TikZSourceSyncScheduler(
        updateRateHz: 20.0
    )

    private init() {}

    func attachSender(_ sender: @escaping ([String: Any]) -> Void) {
        sendCommand = sender
    }

    func activateImageWorkspace() {
        workspace = .image
    }

    func openTikZ(
        path: String,
        source: String,
        previewPNGBase64: String?,
        message: String? = nil
    ) {
        tikzSourceSyncScheduler.cancel()
        latestRevision = 0
        undoTikZSources.removeAll()
        redoTikZSources.removeAll()
        previousHistoryGroup = nil
        refreshHistoryAvailability()
        tikzPath = path
        tikzSource = source
        applyPreview(previewPNGBase64)
        tikzStatus = message ?? "Live — \(path)"
        workspace = .tikz
    }

    func updateTikZSource(_ source: String, historyGroup: String? = nil) {
        guard tikzPath?.isEmpty == false, source != tikzSource else { return }
        let now = ProcessInfo.processInfo.systemUptime
        let isContinuation = historyGroup != nil
            && historyGroup == previousHistoryGroup
            && now - lastGroupedEditAt < 0.55
        if !isContinuation {
            undoTikZSources.append(tikzSource)
            if undoTikZSources.count > maximumHistoryDepth {
                undoTikZSources.removeFirst()
            }
        }
        redoTikZSources.removeAll()
        previousHistoryGroup = historyGroup
        lastGroupedEditAt = now
        refreshHistoryAvailability()
        applyLocalTikZSource(source)
    }

    func undoTikZ() {
        guard let prior = undoTikZSources.popLast() else { return }
        redoTikZSources.append(tikzSource)
        previousHistoryGroup = nil
        refreshHistoryAvailability()
        applyLocalTikZSource(prior)
    }

    func redoTikZ() {
        guard let next = redoTikZSources.popLast() else { return }
        undoTikZSources.append(tikzSource)
        previousHistoryGroup = nil
        refreshHistoryAvailability()
        applyLocalTikZSource(next)
    }

    private func refreshHistoryAvailability() {
        canUndoTikZ = !undoTikZSources.isEmpty
        canRedoTikZ = !redoTikZSources.isEmpty
    }

    private func applyLocalTikZSource(_ source: String) {
        // Update the vector canvas synchronously; throttle only Ubuntu uploads.
        tikzSource = source
        tikzStatus = "Saving TikZ…"
        tikzSourceSyncScheduler.submit { [weak self] in
            self?.sendLatestTikZSource()
        }
    }

    func requestTikZRender() {
        guard let path = tikzPath, !path.isEmpty else {
            return
        }
        tikzSourceSyncScheduler.flush()
        sendCommand?([
            "type": "render_tikz",
            "path": path,
        ])
        tikzStatus = "Rendering TikZ…"
    }

    func applyTikZResponse(
        path: String?,
        source: String?,
        previewPNGBase64: String?,
        clientRevision: Int?,
        message: String?
    ) {
        if let path, !path.isEmpty {
            tikzPath = path
        }

        let revision = clientRevision ?? 0
        let responseIsCurrent = revision == 0 || revision >= latestRevision
        guard responseIsCurrent else {
            return
        }

        // A save ACK can arrive while a newer local edit is waiting for the
        // 20 Hz uploader. Never let that echoed older source overwrite the
        // newer vector state that is already visible on the iPad.
        if let source,
           (revision == 0 || source == tikzSource) {
            tikzSource = source
        }

        applyPreview(previewPNGBase64)

        if revision > 0 && tikzSourceSyncScheduler.hasPendingUpdate {
            tikzStatus = "Saving TikZ…"
        } else {
            tikzStatus = message ?? "TikZ saved"
        }
    }

    func showTikZError(_ message: String) {
        tikzStatus = message
    }

    func closeTikZ() {
        tikzSourceSyncScheduler.flush()
        workspace = .image
        undoTikZSources.removeAll()
        redoTikZSources.removeAll()
        previousHistoryGroup = nil
        refreshHistoryAvailability()
        tikzPath = nil
        tikzSource = ""
        tikzPreviewImage = nil
        tikzStatus = ""
        latestRevision = 0
    }

    private func sendLatestTikZSource() {
        guard let path = tikzPath, !path.isEmpty else {
            return
        }

        let revision = nextRevision
        nextRevision += 1
        latestRevision = revision
        sendCommand?([
            "type": "update_tikz",
            "path": path,
            "source": tikzSource,
            "client_revision": revision,
        ])
    }

    private func applyPreview(_ base64: String?) {
        guard let base64,
              let data = Data(base64Encoded: base64),
              let image = UIImage(data: data) else {
            return
        }
        tikzPreviewImage = image
    }
}
