// Runs the native iPad bridge listener, message transport, graphic saves, and diagnostics.
// The same reverse TCP connection also carries TikZ editor messages.

import Foundation
import Network
import PencilKit
import SwiftUI
import UIKit

/// Native iPad side of the Mind Mirror graphic bridge using an inbound TCP listener.
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
    private var backgroundImageCache: [String: UIImage] = [:]
    private var shouldMaintainListener = false
    private var applicationIsActive = true
    private var listenerRecoveryTask: Task<Void, Never>?
    private var applicationWillResignActiveObserver: NSObjectProtocol?
    private var applicationDidBecomeActiveObserver: NSObjectProtocol?

    private let manualRestartDelayNanoseconds: UInt64 = 200_000_000
    private let wakeRestartDelayNanoseconds: UInt64 = 600_000_000
    private let failedListenerRetryDelayNanoseconds: UInt64 = 1_000_000_000

    private var advertisedVersion: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "0.31.54"
    }

    init() {
        token = UserDefaults.standard.string(forKey: "graphic.bridge.token") ?? ""
        prepareDiagnosticFile()
        appendDiagnostic("ND Graphic initialized")
        appendDiagnostic("Transport mode=inbound TCP listener; Ubuntu connects to the iPad")
        appendEnvironmentDiagnostics()
        startPathMonitor()
        GraphicEditorSessionRouter.shared.attachSender { [weak self] payload in
            self?.send(payload)
        }

        applicationWillResignActiveObserver = NotificationCenter.default.addObserver(
            forName: UIApplication.willResignActiveNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor [weak self] in
                self?.prepareForApplicationSuspension()
            }
        }

        applicationDidBecomeActiveObserver = NotificationCenter.default.addObserver(
            forName: UIApplication.didBecomeActiveNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor [weak self] in
                self?.resumeListeningAfterWake()
            }
        }
    }

    deinit {
        listenerRecoveryTask?.cancel()
        listener?.cancel()
        connection?.cancel()
        pathMonitor?.cancel()
        if let applicationWillResignActiveObserver {
            NotificationCenter.default.removeObserver(applicationWillResignActiveObserver)
        }
        if let applicationDidBecomeActiveObserver {
            NotificationCenter.default.removeObserver(applicationDidBecomeActiveObserver)
        }
    }

    func connect() {
        shouldMaintainListener = true
        applicationIsActive = true
        selectedPath = nil
        document = nil
        drawing = PKDrawing()
        documentToken += 1
        GraphicEditorSessionRouter.shared.closeTikZ()
        UserDefaults.standard.set(token, forKey: "graphic.bridge.token")
        appendDiagnostic("START LISTENER pressed port=\(listenerPort)")
        appendEnvironmentDiagnostics()
        scheduleListenerRecovery(
            reason: "manual start",
            delayNanoseconds: manualRestartDelayNanoseconds,
            resetTransport: true
        )
    }

    private func prepareForApplicationSuspension() {
        guard shouldMaintainListener else { return }

        applicationIsActive = false
        cancelListenerRecovery()
        appendDiagnostic(
            "Application leaving active state; closing listener before suspension so Ubuntu can reconnect cleanly"
        )
        stopTransport(keepStatus: true)
        status = "Paused while iPad sleeps — reconnects automatically on wake"
    }

    private func resumeListeningAfterWake() {
        guard shouldMaintainListener else { return }

        applicationIsActive = true
        appendDiagnostic(
            "Application became active; scheduling fresh listener after Network.framework/Wi-Fi wake"
        )
        scheduleListenerRecovery(
            reason: "application wake",
            delayNanoseconds: wakeRestartDelayNanoseconds,
            resetTransport: true
        )
    }

    private func scheduleListenerRecovery(
        reason: String,
        delayNanoseconds: UInt64,
        resetTransport: Bool
    ) {
        guard shouldMaintainListener, applicationIsActive else { return }

        cancelListenerRecovery()
        if resetTransport {
            stopTransport(keepStatus: true)
        }

        status = "Recovering iPad listener…"
        appendDiagnostic(
            "Scheduling listener recovery reason=\(reason) delay_ms=\(delayNanoseconds / 1_000_000)"
        )

        listenerRecoveryTask = Task { @MainActor [weak self] in
            guard let self else { return }
            if delayNanoseconds > 0 {
                do {
                    try await Task.sleep(nanoseconds: delayNanoseconds)
                } catch {
                    return
                }
            }

            guard !Task.isCancelled,
                  self.shouldMaintainListener,
                  self.applicationIsActive else {
                return
            }

            self.listenerRecoveryTask = nil
            self.startListener()
        }
    }

    private func cancelListenerRecovery() {
        listenerRecoveryTask?.cancel()
        listenerRecoveryTask = nil
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

    /// Returns the last valid background for the active document, including the in-memory safety cache.
    func backgroundImageForCurrentDocument() -> UIImage? {
        guard let path = selectedPath else { return nil }
        return resolvedBackgroundImage(path: path, document: document)
    }

    private func startListener() {
        guard shouldMaintainListener, applicationIsActive else {
            appendDiagnostic("Listener start skipped because app is inactive or listening was disabled")
            return
        }
        guard listener == nil else {
            appendDiagnostic("Listener start skipped because a listener already exists")
            return
        }
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
                        self.scheduleListenerRecovery(
                            reason: "listener waiting: \(Self.describe(error))",
                            delayNanoseconds: self.failedListenerRetryDelayNanoseconds,
                            resetTransport: true
                        )
                    case .ready:
                        self.cancelListenerRecovery()
                        self.status = "Listening on iPad port \(self.listenerPort) — waiting for Ubuntu"
                    case .failed(let error):
                        self.status = "Listener failed: \(Self.describe(error))"
                        self.listener = nil
                        self.scheduleListenerRecovery(
                            reason: "listener failed: \(Self.describe(error))",
                            delayNanoseconds: self.failedListenerRetryDelayNanoseconds,
                            resetTransport: false
                        )
                    case .cancelled:
                        if !self.isConnected && self.shouldMaintainListener && self.applicationIsActive {
                            self.status = "Listener restarting…"
                        } else if !self.isConnected {
                            self.status = "Listener stopped"
                        }
                    default:
                        self.status = "Listener state changed"
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
            listener = nil
            status = "Could not start iPad listener: \(error.localizedDescription)"
            appendDiagnostic(status)
            scheduleListenerRecovery(
                reason: "listener creation failed: \(error.localizedDescription)",
                delayNanoseconds: failedListenerRetryDelayNanoseconds,
                resetTransport: false
            )
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
                        "version": self.advertisedVersion,
                        "token": self.token,
                        "capabilities": ["heartbeat_pong"]
                    ])
                case .waiting(let error):
                    self.isConnected = false
                    self.status = "Accepted connection waiting: \(Self.describe(error))"
                case .failed(let error):
                    self.isConnected = false
                    self.status = "Ubuntu connection failed: \(Self.describe(error))"
                    if self.connection === current { self.connection = nil }
                case .cancelled:
                    self.isConnected = false
                    if self.connection === current { self.connection = nil }
                    if self.listener != nil {
                        self.status = "Listening on iPad port \(self.listenerPort) — waiting for Ubuntu"
                    }
                default:
                    self.isConnected = false
                    self.status = "Ubuntu connection state changed"
                }
            }
        }
        incoming.start(queue: networkQueue)
    }

    func disconnect() {
        shouldMaintainListener = false
        cancelListenerRecovery()
        selectedPath = nil
        document = nil
        drawing = PKDrawing()
        documentToken += 1
        GraphicEditorSessionRouter.shared.closeTikZ()
        stopTransport(keepStatus: false)
    }

    private func stopTransport(keepStatus: Bool) {
        connection?.stateUpdateHandler = nil
        connection?.cancel()
        connection = nil
        listener?.stateUpdateHandler = nil
        listener?.cancel()
        listener = nil
        receiveBuffer.removeAll(keepingCapacity: false)
        isConnected = false
        if !keepStatus { status = "Listener stopped" }
    }

    /// Saves a composite while refusing to turn a valid update document into an accidental empty white image.
    func save(
        drawing: PKDrawing,
        backgroundImage: UIImage?,
        logicalCanvasSize: CGSize,
        pencil: PencilSettings,
        persistBackground: Bool = false
    ) {
        guard let path = selectedPath else { return }
        let imageObjects = CanvasImageObjectStore.load(documentIdentifier: path)

        let effectiveBackgroundImage: UIImage?
        if persistBackground {
            effectiveBackgroundImage = backgroundImage
            if let backgroundImage {
                backgroundImageCache[path] = backgroundImage
            } else {
                backgroundImageCache.removeValue(forKey: path)
            }
        } else {
            effectiveBackgroundImage = backgroundImage ?? resolvedBackgroundImage(path: path, document: document)
        }

        if currentOperation == "update",
           effectiveBackgroundImage == nil,
           drawing.strokes.isEmpty,
           imageObjects.isEmpty {
            status = "Save blocked — original image background is not available"
            appendDiagnostic("Blocked empty update for \(path); preserving existing desktop image")
            return
        }

        guard let png = GraphicImageRenderer.pngData(
            drawing: drawing,
            backgroundImage: effectiveBackgroundImage,
            imageObjects: imageObjects,
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
            "pencil": ["width": pencil.width, "color": pencil.color.hexRGB()],
            "client_revision": revision
        ]
        if let objectData = try? JSONEncoder().encode(imageObjects),
           let objectJSON = try? JSONSerialization.jsonObject(with: objectData) {
            payload["image_objects"] = objectJSON
        }

        if persistBackground {
            payload["background_image_base64"] =
                effectiveBackgroundImage?.pngData()?.base64EncodedString() ?? ""
        }
        send(payload)
        status = "Saving…"
    }

    /// Persists only logical canvas dimensions. No PNG is rendered or replaced.
    /// This keeps canvas resizing lightweight and makes it impossible for a resize
    /// operation by itself to turn an existing source image into a white bitmap.
    func saveCanvasSize(logicalCanvasSize: CGSize) {
        guard let path = selectedPath else { return }
        let width = max(Int(logicalCanvasSize.width.rounded()), 64)
        let height = max(Int(logicalCanvasSize.height.rounded()), 64)

        latestSentRevision += 1
        let revision = latestSentRevision
        send([
            "type": "update_graphic",
            "path": path,
            "canvas_width": width,
            "canvas_height": height,
            "client_revision": revision
        ])

        if var currentDocument = document {
            currentDocument.canvasWidth = width
            currentDocument.canvasHeight = height
            document = currentDocument
        }
        status = "Canvas size saved — \(width) × \(height)"
        appendDiagnostic("Canvas metadata update path=\(path) size=\(width)x\(height) revision=\(revision)")
    }

    private func resolvedBackgroundImage(
        path: String,
        document: GraphicDocumentPayload?
    ) -> UIImage? {
        if let image = GraphicDocumentStore.backgroundImage(from: document) {
            backgroundImageCache[path] = image
            return image
        }
        return backgroundImageCache[path]
    }

    private func cacheBackgroundFromRemote(_ message: GraphicEnvelope) {
        guard let path = message.path else { return }
        if let image = GraphicDocumentStore.backgroundImage(from: message.document) {
            backgroundImageCache[path] = image
            return
        }

        let drawingData = message.document?.drawingDataBase64 ?? ""
        let objects = message.document?.imageObjects ?? []
        guard drawingData.isEmpty, objects.isEmpty,
              let encoded = message.pngBase64,
              let data = Data(base64Encoded: encoded),
              let image = UIImage(data: data) else { return }
        backgroundImageCache[path] = image
    }

    private func receiveNext(on connection: NWConnection) {
        connection.receive(minimumIncompleteLength: 1, maximumLength: 1024 * 1024) {
            [weak self, weak connection] data, _, isComplete, error in
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
            case "heartbeat_ping":
                send(["type": "heartbeat_pong"])
            case "open_graphic":
                GraphicEditorSessionRouter.shared.activateImageWorkspace()
                applyRemote(message, statusPrefix: "Live")
                acknowledgeOpen(message)
            case "graphic_saved":
                status = "Saved — \(message.path ?? "graphic")"
            case "graphic_updated":
                if message.path == selectedPath {
                    status = "Saved — \(message.path ?? "graphic")"
                    break
                }
                if let revision = message.clientRevision,
                   revision > 0,
                   revision <= latestSentRevision {
                    status = "Saved — \(message.path ?? "graphic")"
                    break
                }
                GraphicEditorSessionRouter.shared.activateImageWorkspace()
                applyRemote(message, statusPrefix: "Updated")
            case "open_tikz":
                let path = message.path ?? "tikz.tex"
                GraphicEditorSessionRouter.shared.openTikZ(
                    path: path,
                    source: message.source ?? "",
                    previewPNGBase64: message.previewPNGBase64,
                    message: message.message
                )
                status = "TikZ — \(path)"
            case "tikz_saved", "tikz_updated", "tikz_rendered":
                GraphicEditorSessionRouter.shared.applyTikZResponse(
                    path: message.path,
                    source: message.source,
                    previewPNGBase64: message.previewPNGBase64,
                    clientRevision: message.clientRevision,
                    message: message.message ?? (message.type == "tikz_saved" ? "TikZ saved" : nil)
                )
                status = message.message ?? "TikZ saved"
            case "tikz_error":
                let text = message.message ?? "TikZ bridge error"
                GraphicEditorSessionRouter.shared.showTikZError(text)
                status = text
            case "error":
                status = message.message ?? "Bridge error"
                if GraphicEditorSessionRouter.shared.workspace == .tikz {
                    GraphicEditorSessionRouter.shared.showTikZError(status)
                }
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
        cacheBackgroundFromRemote(message)
        selectedPath = message.path
        currentOperation = message.operation == "insert" ? "insert" : "update"
        document = message.document
        drawing = GraphicDocumentStore.drawing(from: message.document)
        documentToken += 1
        status = "\(statusPrefix) — \(message.path ?? "graphic")"
    }

    private func acknowledgeOpen(_ message: GraphicEnvelope) {
        guard let deliveryID = message.deliveryID, !deliveryID.isEmpty else { return }
        send([
            "type": "open_graphic_ack",
            "path": message.path ?? "",
            "delivery_id": deliveryID
        ])
        appendDiagnostic(
            "Acknowledged open_graphic path=\(message.path ?? "graphic") delivery_id=\(deliveryID)"
        )
    }

    func requestOpen(path: String) {
        guard !path.isEmpty else { return }
        send(["type": "open_recent_graphic", "path": path])
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
                        self.appendDiagnostic("Inbound TCP send failed=\(Self.describe(error))")
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
        case .cancelled:
            return "cancelled"
        default: return "other"
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
        default: return "other"
        }
    }

    private static func describe(_ error: NWError) -> String {
        switch error {
        case .posix(let code): return "POSIX \(code.rawValue): \(code)"
        case .dns(let code): return "DNS \(code)"
        case .tls(let status): return "TLS \(status)"
        default: return String(describing: error)
        }
    }

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
                default: reason = String(describing: path.unsatisfiedReason)
                }
            } else {
                reason = "none"
            }
            let line = "NWPath status=\(path.status) reason=\(reason) wifi=\(path.usesInterfaceType(.wifi)) expensive=\(path.isExpensive) constrained=\(path.isConstrained) interfaces=[\(interfaces)]"
            Task { @MainActor [weak self] in
                guard let self else { return }
                self.appendDiagnostic(line)
                if path.status == .satisfied,
                   self.shouldMaintainListener,
                   self.applicationIsActive,
                   self.listener == nil {
                    self.scheduleListenerRecovery(
                        reason: "network path became satisfied",
                        delayNanoseconds: self.manualRestartDelayNanoseconds,
                        resetTransport: false
                    )
                }
            }
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
        diagnostics = diagnostics.isEmpty ? line : diagnostics + "\n" + line
        writeDiagnosticFile()
    }

    private func prepareDiagnosticFile() {
        let fileManager = FileManager.default
        let base = fileManager.urls(for: .documentDirectory, in: .userDomainMask).first
            ?? fileManager.temporaryDirectory
        let url = base.appendingPathComponent("nd_graphic_diagnostics.log")
        diagnosticFileURL = url
        try? "".write(to: url, atomically: true, encoding: .utf8)
    }

    private func writeDiagnosticFile() {
        guard let url = diagnosticFileURL else { return }
        try? diagnostics.write(to: url, atomically: true, encoding: .utf8)
    }
}
