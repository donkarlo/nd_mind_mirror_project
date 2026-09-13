// WebSocket client for the separate TikZ bridge; raster-image state is never shared.

import Foundation
import SwiftUI
import UIKit

@MainActor
final class TikZBridgeClient: ObservableObject {
    private static let legacyDefaultServerURL = "ws://ubuntu.local:8765/ws"
    private static let defaultServerURL = "ws://donkarlo-uni-laptop.local:8765/ws"

    @Published var serverURL: String
    @Published private(set) var isConnected = false
    @Published private(set) var files: [String] = []
    @Published private(set) var selectedPath: String?
    @Published var source: String = ""
    @Published private(set) var previewImage: UIImage?
    @Published private(set) var status: String = "Disconnected"
    @Published private(set) var desktopOpenToken = 0

    private var socket: URLSessionWebSocketTask?
    private var receiveTask: Task<Void, Never>?
    private var nextRevision = 1
    private var selectedRevision = 0

    init() {
        let saved = UserDefaults.standard.string(forKey: "tikz.bridge.serverURL")
        if let saved, !saved.isEmpty, saved != Self.legacyDefaultServerURL {
            serverURL = saved
        } else {
            serverURL = Self.defaultServerURL
        }
    }

    func connect() {
        disconnect()
        guard let url = URL(string: serverURL) else {
            status = "Invalid TikZ bridge URL"
            return
        }
        UserDefaults.standard.set(serverURL, forKey: "tikz.bridge.serverURL")
        let task = URLSession.shared.webSocketTask(with: url)
        socket = task
        task.resume()
        status = "Connecting…"
        startReceiveLoop(task)
    }

    func disconnect() {
        receiveTask?.cancel()
        receiveTask = nil
        socket?.cancel(with: .goingAway, reason: nil)
        socket = nil
        isConnected = false
        status = "Disconnected"
    }

    func refreshFiles() {
        guard isConnected else { return }
        send(["type": "list_files"])
    }

    func openFile(_ path: String) {
        guard isConnected else {
            status = "TikZ bridge is not connected"
            return
        }
        selectedPath = path
        selectedRevision = 0
        status = "Loading \(path)…"
        send(["type": "open_file", "path": path])
    }

    func updateSource(_ newSource: String) {
        guard isConnected, let path = selectedPath else { return }
        source = newSource
        let revision = nextRevision
        nextRevision += 1
        selectedRevision = revision
        send([
            "type": "update_source",
            "path": path,
            "source": newSource,
            "client_revision": revision,
        ])
        status = "Saving and rendering…"
    }

    func requestRender() {
        guard isConnected, let path = selectedPath else { return }
        send(["type": "render", "path": path])
    }

    private func startReceiveLoop(_ task: URLSessionWebSocketTask) {
        receiveTask = Task { [weak self] in
            guard let self else { return }
            do {
                while !Task.isCancelled {
                    let message = try await task.receive()
                    let text: String
                    switch message {
                    case .string(let value): text = value
                    case .data(let data): text = String(decoding: data, as: UTF8.self)
                    @unknown default: continue
                    }
                    self.handle(text)
                }
            } catch {
                if !Task.isCancelled {
                    self.isConnected = false
                    self.status = "TikZ connection failed: \(error.localizedDescription)"
                }
            }
        }
    }

    private func handle(_ text: String) {
        guard let data = text.data(using: .utf8) else { return }
        do {
            let envelope = try JSONDecoder().decode(TikZBridgeEnvelope.self, from: data)
            switch envelope.type {
            case "hello":
                isConnected = true
                status = "TikZ bridge connected"
                send(["type": "list_files"])
            case "desktop_open":
                if let path = envelope.path {
                    desktopOpenToken += 1
                    openFile(path)
                }
            case "file_list":
                files = envelope.files ?? []
                status = "\(files.count) TikZ files"
            case "file_opened", "file_updated", "external_change", "rendered":
                guard let path = envelope.path, selectedPath == nil || selectedPath == path else { return }
                selectedPath = path
                if let remoteSource = envelope.source {
                    if envelope.clientRevision == nil || envelope.clientRevision == 0 || (envelope.clientRevision ?? 0) >= selectedRevision {
                        source = remoteSource
                    }
                }
                applyPreview(envelope.previewPNGBase64)
                status = envelope.message ?? "Live — \(path)"
            case "render_error", "error":
                status = envelope.message ?? "TikZ bridge error"
            default:
                break
            }
        } catch {
            status = "Invalid TikZ bridge message: \(error.localizedDescription)"
        }
    }

    private func applyPreview(_ base64: String?) {
        guard let base64,
              let data = Data(base64Encoded: base64),
              let image = UIImage(data: data) else { return }
        previewImage = image
    }

    private func send(_ object: [String: Any]) {
        guard let socket else { return }
        do {
            let data = try JSONSerialization.data(withJSONObject: object)
            let text = String(decoding: data, as: UTF8.self)
            Task {
                do {
                    try await socket.send(.string(text))
                } catch {
                    await MainActor.run {
                        self.isConnected = false
                        self.status = "TikZ send failed: \(error.localizedDescription)"
                    }
                }
            }
        } catch {
            status = "Could not encode TikZ bridge message"
        }
    }
}
