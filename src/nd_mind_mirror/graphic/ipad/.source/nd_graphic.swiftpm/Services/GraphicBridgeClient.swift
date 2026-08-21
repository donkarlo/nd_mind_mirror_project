import Foundation
import Network
import PencilKit
import SwiftUI
import UIKit

/// Native iPad side of the Mind Mirror graphic bridge.
///
/// iPadOS local-network privacy blocks *outgoing* connections when the Swift
/// Playgrounds dev runner gets into an inconsistent permission state. Apple
/// documents that listening for and accepting an incoming TCP connection does
/// not require Local Network privilege. Therefore this build reverses the
/// direction: ND Graphic listens on the iPad and the Ubuntu bridge finds and
/// connects to it.
@MainActor
final class GraphicBridgeClient: ObservableObject {
    @Published var isConnected = false
    @Published var status = "Listener stopped"
    @Published var selectedPath: String?
    @Published var currentOperation = "update"
    @Published var document: GraphicDocumentPayload?
    @Published var drawing = PKDrawing()
    @Published var documentToken = 0
    @Published var endpoint = "listen://0.0.0.0:8768"
    @Published var token: String
    @Published var diagnostics = ""
    @Published var diagnosticFileURL: URL?

    private var listener: NWListener?
    private var connection: NWConnection?
    private let networkQueue = DispatchQueue(label: "nd.mindmirror.graphic.inboundtcp")
    private var receiveBuffer = Data()
    private var latestSentRevision = 0
    private let maximumBufferedBytes = 128 * 1024 * 1024
    private let listenerPort: UInt16 = 8768
    private var pathMonitor: NWPathMonitor?
    private let pathMonitorQueue = DispatchQueue(label: "nd.graphic.network.path")
    private let diagnosticStartedAt = Date()

    init() {
        token = UserDefaults.standard.string(forKey: "graphic.bridge.token") ?? ""
        prepareDiagnosticFile()
        appendDiagnostic("ND Graphic 0.30.10 initialized")
        appendDiagnostic("Transport mode=inbound TCP listener; no outgoing LAN connection is made by the iPad")
        appendEnvironmentDiagnostics()
        startPathMonitor()
    }

    deinit {
        listener?.cancel()
        connection?.cancel()
        pathMonitor?.cancel()
    }

    func connect() {
        disconnect(keepStatus: true)
        UserDefaults.standard.set(token, forKey: "graphic.bridge.token")
        appendDiagnostic("START LISTENER pressed port=\(listenerPort)")
        appendEnvironmentDiagnostics()
        startListener()
    }

    func runDiagnostics() {
        appendDiagnostic("Manual diagnostics requested")
        appendEnvironmentDiagnostics()
        appendDiagnostic("listener=\(listener == nil ? "nil" : "active") connection=\(connection == nil ? "nil" : "present")")
    }

    func clearDiagnostics() {
        diagnostics = ""
        writeDiagnosticFile()
        appendDiagnostic("Diagnostic log cleared")
    }

    func copyableDiagnostics() -> String {
        diagnostics
    }

    private func startListener() {
        guard let port = NWEndpoint.Port(rawValue: listenerPort) else {
            status = "Invalid listener port"
            appendDiagnostic(status)
            return
        }

        do {
            let parameters = NWParameters.tcp
            parameters.allowLocalEndpointReuse = true
            let newListener = try NWListener(using: parameters, on: port)
            listener = newListener
            status = "Starting iPad listener on port \(listenerPort)…"

            newListener.stateUpdateHandler = { [weak self, weak newListener] state in
                Task { @MainActor in
                    guard let self, let current = newListener, self.listener === current else { return }
                    self.appendDiagnostic("iPad listener state=\(Self.describeListenerState(state))")
                    switch state {
                    case .setup:
                        self.status = "Preparing iPad listener…"
                    case .waiting(let error):
                        self.status = "Listener waiting: \(Self.describe(error))"
                    case .ready:
                        self.status = "Listening on iPad port \(self.listenerPort) — waiting for Ubuntu"
                    case .failed(let error):
                        self.status = "Listener failed: \(Self.describe(error))"
                        self.listener = nil
                    case .cancelled:
                        if !self.isConnected {
                            self.status = "Listener stopped"
                        }
                    @unknown default:
                        self.status = "Unknown listener state"
                    }
                }
            }

            newListener.newConnectionHandler = { [weak self] incoming in
                Task { @MainActor in
                    self?.accept(incoming)
                }
            }
            newListener.start(queue: networkQueue)
        } catch {
            status = "Could not start iPad listener: \(error.localizedDescription)"
            appendDiagnostic(status)
        }
    }

    private func accept(_ incoming: NWConnection) {
        appendDiagnostic("Ubuntu connection arrived endpoint=\(String(describing: incoming.endpoint))")

        if let old = connection {
            old.stateUpdateHandler = nil
            old.cancel()
        }
        receiveBuffer.removeAll(keepingCapacity: true)
        connection = incoming

        incoming.stateUpdateHandler = { [weak self, weak incoming] state in
            Task { @MainActor in
                guard let self, let current = incoming, self.connection === current else { return }
                self.appendDiagnostic("Accepted TCP state=\(Self.describeConnectionState(state))")
                switch state {
                case .setup:
                    self.status = "Ubuntu connection preparing…"
                case .preparing:
                    self.status = "Ubuntu is connecting…"
                case .ready:
                    self.status = "Ubuntu connected — negotiating bridge…"
                    self.receiveNext(on: current)
                    self.send([
                        "type": "ipad_listener",
                        "version": "0.30.10",
                        "token": self.token
                    ])
                case .waiting(let error):
                    self.isConnected = false
                    self.status = "Accepted connection waiting: \(Self.describe(error))"
                case .failed(let error):
                    self.isConnected = false
                    self.status = "Ubuntu connection failed: \(Self.describe(error))"
                    if self.connection === current {
                        self.connection = nil
                    }
                case .cancelled:
                    self.isConnected = false
                    if self.connection === current {
                        self.connection = nil
                    }
                    if self.listener != nil {
                        self.status = "Listening on iPad port \(self.listenerPort) — waiting for Ubuntu"
                    }
                @unknown default:
                    self.isConnected = false
                }
            }
        }
        incoming.start(queue: networkQueue)
    }

    func disconnect() {
        selectedPath = nil
        document = nil
        drawing = PKDrawing()
        documentToken += 1
        disconnect(keepStatus: false)
    }

    private func disconnect(keepStatus: Bool) {
        connection?.stateUpdateHandler = nil
        connection?.cancel()
        connection = nil
        listener?.stateUpdateHandler = nil
        listener?.cancel()
        listener = nil
        receiveBuffer.removeAll(keepingCapacity: false)
        isConnected = false
        if !keepStatus {
            status = "Listener stopped"
        }
    }

    func save(
        drawing: PKDrawing,
        backgroundImage: UIImage?,
        logicalCanvasSize: CGSize,
        pencil: PencilSettings,
        persistBackground: Bool = false
    ) {
        guard let path = selectedPath else { return }
        guard let png = GraphicImageRenderer.pngData(
            drawing: drawing,
            backgroundImage: backgroundImage,
            logicalCanvasSize: logicalCanvasSize
        ) else {
            status = "Could not render PNG"
            return
        }

        latestSentRevision += 1
        let revision = latestSentRevision
        var payload: [String: Any] = [
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
        ]
        if persistBackground {
            payload["background_image_base64"] = backgroundImage?.pngData()?.base64EncodedString() ?? ""
        }
        send(payload)
        status = "Saving…"
    }

    private func receiveNext(on connection: NWConnection) {
        connection.receive(
            minimumIncompleteLength: 1,
            maximumLength: 1024 * 1024
        ) { [weak self, weak connection] data, _, isComplete, error in
            Task { @MainActor in
                guard let self, let current = connection, self.connection === current else { return }

                if let data, !data.isEmpty {
                    self.appendDiagnostic("Inbound TCP RX bytes=\(data.count)")
                    self.receiveBuffer.append(data)
                    if self.receiveBuffer.count > self.maximumBufferedBytes {
                        self.status = "Bridge message exceeded 128 MB"
                        self.appendDiagnostic(self.status)
                        self.disconnect()
                        return
                    }
                    self.consumeCompleteLines()
                }

                if let error {
                    self.isConnected = false
                    self.status = "Connection lost: \(Self.describe(error))"
                    self.appendDiagnostic("Inbound TCP receive error=\(Self.describe(error))")
                    current.cancel()
                    return
                }
                if isComplete {
                    self.isConnected = false
                    self.status = "Ubuntu disconnected — still listening"
                    self.appendDiagnostic("Ubuntu closed accepted TCP connection")
                    current.cancel()
                    return
                }
                self.receiveNext(on: current)
            }
        }
    }

    private func consumeCompleteLines() {
        while let newline = receiveBuffer.firstIndex(of: 0x0A) {
            let line = receiveBuffer.prefix(upTo: newline)
            receiveBuffer.removeSubrange(...newline)
            guard !line.isEmpty else { continue }
            guard let text = String(data: Data(line), encoding: .utf8) else {
                status = "Received invalid UTF-8 from bridge"
                appendDiagnostic(status)
                continue
            }
            appendDiagnostic("Inbound TCP RX JSON bytes=\(line.count)")
            handle(text)
        }
    }

    private func handle(_ text: String) {
        guard let data = text.data(using: .utf8) else { return }
        do {
            let message = try JSONDecoder().decode(GraphicEnvelope.self, from: data)
            appendDiagnostic("Bridge message type=\(message.type)")
            switch message.type {
            case "hello":
                isConnected = true
                status = "Connected — waiting for Mind Mirror"
                appendDiagnostic("Ubuntu hello received; reverse connection is READY")
                send(["type": "request_current"])
            case "open_graphic":
                applyRemote(message, statusPrefix: "Live")
            case "graphic_saved":
                status = "Saved — \(message.path ?? "graphic")"
            case "graphic_updated":
                if let revision = message.clientRevision,
                   revision > 0,
                   revision <= latestSentRevision {
                    status = "Saved — \(message.path ?? "graphic")"
                    break
                }
                applyRemote(message, statusPrefix: "Updated")
            case "error":
                status = message.message ?? "Bridge error"
                appendDiagnostic("Bridge error: \(status)")
            default:
                appendDiagnostic("Ignoring unknown bridge message type=\(message.type)")
            }
        } catch {
            status = "Invalid bridge message: \(error.localizedDescription)"
            appendDiagnostic(status)
        }
    }

    private func applyRemote(_ message: GraphicEnvelope, statusPrefix: String) {
        selectedPath = message.path
        currentOperation = message.operation == "insert" ? "insert" : "update"
        document = message.document
        drawing = GraphicDocumentStore.drawing(from: message.document)
        documentToken += 1
        status = "\(statusPrefix) — \(message.path ?? "graphic")"
    }

    private func send(_ object: [String: Any]) {
        guard let connection else {
            appendDiagnostic("TX skipped because accepted connection=nil")
            return
        }
        do {
            var data = try JSONSerialization.data(withJSONObject: object)
            data.append(0x0A)
            appendDiagnostic("Inbound TCP TX type=\(object["type"] ?? "?") bytes=\(data.count)")
            connection.send(
                content: data,
                contentContext: .defaultMessage,
                isComplete: true,
                completion: .contentProcessed { [weak self, weak connection] error in
                    guard let error else { return }
                    Task { @MainActor in
                        guard let self, let current = connection, self.connection === current else { return }
                        self.status = "Send failed: \(Self.describe(error))"
                        self.appendDiagnostic("Inbound TCP send failed: \(Self.describe(error))")
                    }
                }
            )
        } catch {
            status = "Could not encode message"
            appendDiagnostic("JSON encode failed: \(error.localizedDescription)")
        }
    }

    private static func describeListenerState(_ state: NWListener.State) -> String {
        switch state {
        case .setup: return "setup"
        case .waiting(let error): return "waiting(\(describe(error)))"
        case .ready: return "ready"
        case .failed(let error): return "failed(\(describe(error)))"
        case .cancelled: return "cancelled"
        @unknown default: return "unknown"
        }
    }

    private static func describeConnectionState(_ state: NWConnection.State) -> String {
        switch state {
        case .setup: return "setup"
        case .preparing: return "preparing"
        case .ready: return "ready"
        case .waiting(let error): return "waiting(\(describe(error)))"
        case .failed(let error): return "failed(\(describe(error)))"
        case .cancelled: return "cancelled"
        @unknown default: return "unknown"
        }
    }

    private static func describe(_ error: NWError) -> String {
        switch error {
        case .posix(let code): return "POSIX \(code.rawValue): \(code)"
        case .dns(let code): return "DNS \(code)"
        case .tls(let status): return "TLS \(status)"
        @unknown default: return String(describing: error)
        }
    }

    // MARK: - Diagnostics

    private func startPathMonitor() {
        pathMonitor?.cancel()
        let monitor = NWPathMonitor()
        pathMonitor = monitor
        monitor.pathUpdateHandler = { [weak self] path in
            let interfaces = path.availableInterfaces.map { "\($0.name):\($0.type)" }.joined(separator: ",")
            let reason: String
            if path.status == .unsatisfied {
                switch path.unsatisfiedReason {
                case .cellularDenied: reason = "cellularDenied"
                case .wifiDenied: reason = "wifiDenied"
                case .localNetworkDenied: reason = "localNetworkDenied"
                case .notAvailable: reason = "notAvailable"
                @unknown default: reason = "unknown"
                }
            } else {
                reason = "none"
            }
            let line = "NWPath status=\(path.status) reason=\(reason) wifi=\(path.usesInterfaceType(.wifi)) expensive=\(path.isExpensive) constrained=\(path.isConstrained) interfaces=[\(interfaces)]"
            Task { @MainActor [weak self] in self?.appendDiagnostic(line) }
        }
        monitor.start(queue: pathMonitorQueue)
    }

    private func appendEnvironmentDiagnostics() {
        let bundle = Bundle.main
        appendDiagnostic("bundle id=\(bundle.bundleIdentifier ?? "nil") version=\(bundle.object(forInfoDictionaryKey: "CFBundleShortVersionString") ?? "nil") build=\(bundle.object(forInfoDictionaryKey: "CFBundleVersion") ?? "nil")")
        appendDiagnostic("OS=\(ProcessInfo.processInfo.operatingSystemVersionString)")
        appendDiagnostic("listenerPort=\(listenerPort)")
        appendDiagnostic("NSLocalNetworkUsageDescription=\(String(describing: bundle.object(forInfoDictionaryKey: "NSLocalNetworkUsageDescription")))")
        appendDiagnostic("NSBonjourServices=\(String(describing: bundle.object(forInfoDictionaryKey: "NSBonjourServices")))")
        appendDiagnostic("NSAppTransportSecurity=\(String(describing: bundle.object(forInfoDictionaryKey: "NSAppTransportSecurity")))")
    }

    func appendDiagnostic(_ message: String) {
        let elapsed = Date().timeIntervalSince(diagnosticStartedAt)
        let line = String(format: "[%8.3fs] %@", elapsed, message)
        if diagnostics.isEmpty {
            diagnostics = line
        } else {
            diagnostics += "\n" + line
        }
        writeDiagnosticFile()
    }

    private func prepareDiagnosticFile() {
        let fm = FileManager.default
        let base = fm.urls(for: .documentDirectory, in: .userDomainMask).first
            ?? fm.temporaryDirectory
        let url = base.appendingPathComponent("nd_graphic_diagnostics.log")
        diagnosticFileURL = url
        try? "".write(to: url, atomically: true, encoding: .utf8)
    }

    private func writeDiagnosticFile() {
        guard let url = diagnosticFileURL else { return }
        try? diagnostics.write(to: url, atomically: true, encoding: .utf8)
    }
}
