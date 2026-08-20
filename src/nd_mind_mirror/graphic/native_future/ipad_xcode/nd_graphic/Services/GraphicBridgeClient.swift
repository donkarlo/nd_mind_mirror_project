import Foundation
import Network
import PencilKit
import SwiftUI

@MainActor
final class GraphicBridgeClient: ObservableObject {
    @Published var isConnected = false
    @Published var status = "Not connected"
    @Published var selectedPath: String?
    @Published var currentOperation = "update"
    @Published var document: GraphicDocumentPayload?
    @Published var drawing = PKDrawing()
    @Published var documentToken = 0
    @Published var endpoint: String
    @Published var token: String

    private var connection: NWConnection?
    private let networkQueue = DispatchQueue(label: "nd.mindmirror.graphic.websocket")
    private var latestSentRevision = 0

    init() {
        endpoint = UserDefaults.standard.string(forKey: "graphic.bridge.url")
            ?? "ws://10.0.0.73:8766/ws"
        token = UserDefaults.standard.string(forKey: "graphic.bridge.token") ?? ""
    }

    deinit {
        connection?.cancel()
    }

    func connect() {
        disconnect()
        UserDefaults.standard.set(endpoint, forKey: "graphic.bridge.url")
        UserDefaults.standard.set(token, forKey: "graphic.bridge.token")
        status = "Requesting local network access…"

        LocalNetworkPermissionRequester.shared.request { [weak self] allowed, detail in
            guard let self else { return }
            if !allowed {
                self.status = "Local network access is blocked. Enable ND Graphic in Settings → Privacy & Security → Local Network.\n\(detail ?? \"\")"
                return
            }
            self.openWebSocket()
        }
    }

    private func openWebSocket() {
        guard var components = URLComponents(string: endpoint) else {
            status = "Invalid WebSocket URL"
            return
        }
        if !token.isEmpty {
            var items = components.queryItems ?? []
            items.removeAll { $0.name == "token" }
            items.append(URLQueryItem(name: "token", value: token))
            components.queryItems = items
        }
        guard let url = components.url, url.scheme == "ws" || url.scheme == "wss" else {
            status = "Use a ws:// or wss:// WebSocket URL"
            return
        }

        let webSocketOptions = NWProtocolWebSocket.Options(.version13)
        webSocketOptions.autoReplyPing = true
        webSocketOptions.maximumMessageSize = 64 * 1024 * 1024

        let parameters: NWParameters
        if url.scheme == "wss" {
            let tcp = NWProtocolTCP.Options()
            parameters = NWParameters(tls: NWProtocolTLS.Options(), tcp: tcp)
        } else {
            // Network.framework talks directly to the LAN WebSocket bridge.
            // Unlike URLSession, this path does not route the ws:// load
            // through App Transport Security's URL-loading policy.
            parameters = NWParameters.tcp
        }
        parameters.defaultProtocolStack.applicationProtocols.insert(
            webSocketOptions,
            at: 0
        )

        let newConnection = NWConnection(to: .url(url), using: parameters)
        connection = newConnection
        status = "Connecting to \(url.host ?? \"Ubuntu\")…"

        newConnection.stateUpdateHandler = { [weak self, weak newConnection] state in
            Task { @MainActor in
                guard let self, let current = newConnection else { return }
                guard self.connection === current else { return }
                self.handleConnectionState(state, connection: current)
            }
        }
        newConnection.start(queue: networkQueue)
    }

    private func handleConnectionState(
        _ state: NWConnection.State,
        connection: NWConnection
    ) {
        switch state {
        case .setup:
            status = "Preparing connection…"
        case .preparing:
            status = "Connecting…"
        case .ready:
            isConnected = true
            status = "Connected — waiting for Mind Mirror"
            receiveNext(on: connection)
        case .waiting(let error):
            isConnected = false
            status = "Waiting for local network: \(String(describing: error))"
        case .failed(let error):
            isConnected = false
            status = "Connection failed: \(String(describing: error))"
            if self.connection === connection {
                self.connection = nil
            }
        case .cancelled:
            isConnected = false
            if self.connection === connection {
                self.connection = nil
            }
        @unknown default:
            isConnected = false
        }
    }

    func disconnect() {
        connection?.stateUpdateHandler = nil
        connection?.cancel()
        connection = nil
        isConnected = false
    }

    func save(
        drawing: PKDrawing,
        logicalCanvasSize: CGSize,
        pencil: PencilSettings
    ) {
        guard let path = selectedPath else { return }
        guard let png = GraphicImageRenderer.pngData(
            drawing: drawing,
            logicalCanvasSize: logicalCanvasSize
        ) else {
            status = "Could not render PNG"
            return
        }

        latestSentRevision += 1
        let revision = latestSentRevision
        send([
            "type": "update_graphic",
            "path": path,
            "drawing_data_base64": drawing.dataRepresentation().base64EncodedString(),
            "png_base64": png.base64EncodedString(),
            "canvas_width": Int(logicalCanvasSize.width.rounded()),
            "canvas_height": Int(logicalCanvasSize.height.rounded()),
            "pencil": [
                "width": pencil.width,
                "color": pencil.color.hexRGB()
            ],
            "client_revision": revision
        ])
        status = "Saving…"
    }

    private func receiveNext(on connection: NWConnection) {
        connection.receiveMessage { [weak self, weak connection] data, _, _, error in
            Task { @MainActor in
                guard let self, let current = connection else { return }
                guard self.connection === current else { return }

                if let error {
                    self.isConnected = false
                    self.status = "Connection lost: \(String(describing: error))"
                    return
                }

                if let data, let text = String(data: data, encoding: .utf8) {
                    self.handle(text)
                }
                self.receiveNext(on: current)
            }
        }
    }

    private func handle(_ text: String) {
        guard let data = text.data(using: .utf8) else { return }
        do {
            let message = try JSONDecoder().decode(GraphicEnvelope.self, from: data)
            switch message.type {
            case "hello":
                isConnected = true
                status = "Connected — waiting for Mind Mirror"
                send(["type": "request_current"])
            case "open_graphic":
                applyRemote(message, statusPrefix: "Live")
            case "graphic_updated":
                if let revision = message.clientRevision,
                   revision > 0,
                   revision <= latestSentRevision {
                    status = "Saved — \(message.path ?? \"graphic\")"
                    break
                }
                applyRemote(message, statusPrefix: "Updated")
            case "error":
                status = message.message ?? "Bridge error"
            default:
                break
            }
        } catch {
            status = "Invalid bridge message: \(error.localizedDescription)"
        }
    }

    private func applyRemote(_ message: GraphicEnvelope, statusPrefix: String) {
        selectedPath = message.path
        currentOperation = message.operation == "insert" ? "insert" : "update"
        document = message.document
        drawing = GraphicDocumentStore.drawing(from: message.document)
        documentToken += 1
        status = "\(statusPrefix) — \(message.path ?? \"graphic\")"
    }

    private func send(_ object: [String: Any]) {
        guard let connection else { return }
        do {
            let data = try JSONSerialization.data(withJSONObject: object)
            let metadata = NWProtocolWebSocket.Metadata(opcode: .text)
            let context = NWConnection.ContentContext(
                identifier: "nd-mind-mirror-text",
                metadata: [metadata]
            )
            connection.send(
                content: data,
                contentContext: context,
                isComplete: true,
                completion: .contentProcessed { [weak self, weak connection] error in
                    guard let error else { return }
                    Task { @MainActor in
                        guard let self, let current = connection else { return }
                        guard self.connection === current else { return }
                        self.status = "Send failed: \(String(describing: error))"
                    }
                }
            )
        } catch {
            status = "Could not encode message"
        }
    }
}
