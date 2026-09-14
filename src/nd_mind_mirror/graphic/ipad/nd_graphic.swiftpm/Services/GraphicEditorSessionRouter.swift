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
        tikzPath = path
        tikzSource = source
        applyPreview(previewPNGBase64)
        tikzStatus = message ?? "Live — \(path)"
        workspace = .tikz
    }

    func updateTikZSource(_ source: String) {
        guard let path = tikzPath, !path.isEmpty else { return }
        tikzSource = source
        let revision = nextRevision
        nextRevision += 1
        latestRevision = revision
        sendCommand?([
            "type": "update_tikz",
            "path": path,
            "source": source,
            "client_revision": revision,
        ])
        tikzStatus = "Saving TikZ…"
    }

    func requestTikZRender() {
        guard let path = tikzPath, !path.isEmpty else { return }
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
        if let source, responseIsCurrent {
            tikzSource = source
        }
        if responseIsCurrent {
            applyPreview(previewPNGBase64)
        }
        tikzStatus = message ?? "TikZ saved"
    }

    func showTikZError(_ message: String) {
        tikzStatus = message
    }

    func closeTikZ() {
        workspace = .image
        tikzPath = nil
        tikzSource = ""
        tikzPreviewImage = nil
        tikzStatus = ""
        latestRevision = 0
    }

    private func applyPreview(_ base64: String?) {
        guard let base64,
              let data = Data(base64Encoded: base64),
              let image = UIImage(data: data) else { return }
        tikzPreviewImage = image
    }
}
