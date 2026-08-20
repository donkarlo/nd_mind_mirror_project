import Foundation
import SwiftUI
import UIKit

@MainActor
final class BridgeClient: ObservableObject {
    @Published var serverURL: String = UserDefaults.standard.string(forKey: "bridge.serverURL") ?? "ws://ubuntu.local:8765/ws"
    @Published var token: String = UserDefaults.standard.string(forKey: "bridge.token") ?? ""
    @Published private(set) var isConnected = false
    @Published private(set) var files: [String] = []
    @Published private(set) var selectedPath: String?
    @Published var source: String = ""
    @Published private(set) var previewImage: UIImage?
    @Published private(set) var status: String = "Disconnected"
    @Published private(set) var clearCanvasToken: Int = 0

    private var socket: URLSessionWebSocketTask?
    private var receiveTask: Task<Void, Never>?
    private var nextClientRevision = 1
    private var latestSentRevision = 0

    func connect() {
        disconnect()
        guard var components = URLComponents(string: serverURL) else {
            status = "Invalid WebSocket URL"
            return
        }
        if !token.isEmpty {
            var items = components.queryItems ?? []
            items.append(URLQueryItem(name: "token", value: token))
            components.queryItems = items
        }
        guard let url = components.url else {
            status = "Invalid WebSocket URL"
            return
        }

        UserDefaults.standard.set(serverURL, forKey: "bridge.serverURL")
        UserDefaults.standard.set(token, forKey: "bridge.token")
        let task = URLSession.shared.webSocketTask(with: url)
        socket = task
        task.resume()
        isConnected = true
        status = "Connecting…"
        startReceiveLoop(task)
        send(["type": "list_files"])
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
        send(["type": "list_files"])
    }

    func openFile(_ path: String) {
        selectedPath = path
        status = "Loading \(path)…"
        send(["type": "open_file", "path": path])
    }

    @discardableResult
    func updateSource(_ newSource: String) -> Int {
        guard let path = selectedPath else { return 0 }
        source = newSource
        let revision = nextClientRevision
        nextClientRevision += 1
        latestSentRevision = revision
        send([
            "type": "update_source",
            "path": path,
            "source": newSource,
            "client_revision": revision,
        ])
        status = "Rendering…"
        return revision
    }

    func requestRender() {
        guard let path = selectedPath else { return }
        send(["type": "render", "path": path])
    }

    func reportStatus(_ message: String) {
        status = message
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
                    await self.handle(text)
                }
            } catch {
                if !Task.isCancelled {
                    self.isConnected = false
                    self.status = "Connection lost: \(error.localizedDescription)"
                }
            }
        }
    }

    private func handle(_ text: String) {
        guard let data = text.data(using: .utf8) else { return }
        do {
            let envelope = try JSONDecoder().decode(BridgeEnvelope.self, from: data)
            switch envelope.type {
            case "hello":
                isConnected = true
                status = "Connected"
            case "file_list":
                files = envelope.files ?? []
                status = "Connected — \(files.count) TikZ/TeX files"
            case "file_opened", "file_updated", "external_change", "rendered":
                if let path = envelope.path, selectedPath == nil || selectedPath == path {
                    selectedPath = path
                    if let source = envelope.source { self.source = source }
                    applyPreview(envelope.previewPNGBase64)
                    if let revision = envelope.clientRevision,
                       revision >= latestSentRevision {
                        clearCanvasToken += 1
                    } else if latestSentRevision == 0 && envelope.previewPNGBase64 != nil {
                        clearCanvasToken += 1
                    }
                    status = "Live — \(path)"
                }
            case "render_error", "error":
                status = envelope.message ?? "Bridge error"
            default:
                break
            }
        } catch {
            status = "Invalid bridge message: \(error.localizedDescription)"
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
                        self.status = "Send failed: \(error.localizedDescription)"
                    }
                }
            }
        } catch {
            status = "Could not encode message"
        }
    }
}
