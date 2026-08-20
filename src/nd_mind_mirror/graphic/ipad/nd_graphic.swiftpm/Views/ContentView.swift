import PencilKit
import SwiftUI

struct ContentView: View {
    @StateObject private var bridge = GraphicBridgeClient()
    @State private var tool: GraphicTool = .pencil
    @State private var pencil = PencilSettings()
    @State private var localDrawing = PKDrawing()
    @State private var localToken = -1
    @State private var canvasToken = 0
    @State private var saveTask: Task<Void, Never>?
    @State private var canvasUndoManager: UndoManager?

    var body: some View {
        VStack(spacing: 0) {
            startupBanner

            if !bridge.isConnected {
                connectionScreen
            } else if bridge.selectedPath == nil {
                waitingScreen
            } else {
                drawingScreen
            }
        }
        .background(Color(uiColor: .systemGroupedBackground))
        .onChange(of: bridge.documentToken) { _, token in
            guard token != localToken else { return }
            localToken = token
            localDrawing = bridge.drawing
            canvasToken += 1
            if let remotePencil = bridge.document?.pencil {
                if let width = remotePencil.width {
                    pencil.width = width
                }
                if let color = remotePencil.color {
                    pencil.color = Color(hex: color)
                }
            }
        }
    }

    private var startupBanner: some View {
        HStack(spacing: 10) {
            Image(systemName: "pencil.and.scribble")
            Text("ND Graphic v0.30")
                .font(.headline)
            Spacer()
            Text(bridge.isConnected ? "Connected" : "Not connected")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(.thinMaterial)
    }

    private var connectionScreen: some View {
        ScrollView {
            VStack(spacing: 20) {
                Text("Connect to Mind Mirror")
                    .font(.largeTitle.bold())

                Text("The Ubuntu bridge must be running. Use the Ubuntu computer's LAN address, for example ws://192.168.1.20:8766/ws.")
                    .multilineTextAlignment(.center)
                    .foregroundStyle(.secondary)

                VStack(alignment: .leading, spacing: 12) {
                    Text("Ubuntu bridge")
                        .font(.headline)

                    TextField("ws://192.168.1.20:8766/ws", text: $bridge.endpoint)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .keyboardType(.URL)
                        .textFieldStyle(.roundedBorder)

                    SecureField("Token (optional)", text: $bridge.token)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .textFieldStyle(.roundedBorder)

                    Button {
                        bridge.connect()
                    } label: {
                        Text("Connect")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                }
                .padding(20)
                .background(.background, in: RoundedRectangle(cornerRadius: 18))

                Text(bridge.status)
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .textSelection(.enabled)

                Text("If iPadOS asks whether ND Graphic may find devices on your local network, tap Allow.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }
            .frame(maxWidth: 650)
            .padding(32)
            .frame(maxWidth: .infinity)
        }
    }

    private var waitingScreen: some View {
        VStack(spacing: 18) {
            Spacer()
            Image(systemName: "ipad.and.arrow.forward")
                .font(.system(size: 58))
            Text("Connected")
                .font(.largeTitle.bold())
            Text("Waiting for Insert / Update from Mind Mirror")
                .font(.title3)
            Text("When you choose Insert / update image in iPad… in Source or Visual, the drawing opens here automatically.")
                .multilineTextAlignment(.center)
                .foregroundStyle(.secondary)
                .frame(maxWidth: 620)
            Text(bridge.status)
                .font(.caption)
                .foregroundStyle(.secondary)
            Button("Disconnect") {
                bridge.disconnect()
            }
            .buttonStyle(.bordered)
            Spacer()
        }
        .padding(32)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var drawingScreen: some View {
        VStack(spacing: 0) {
            toolbar
            GeometryReader { proxy in
                let logical = logicalCanvasSize
                let fitted = fittedCanvas(logical: logical, available: proxy.size)
                ZStack {
                    Color(uiColor: .secondarySystemBackground)
                    PencilCanvasView(
                        drawing: localDrawing,
                        documentToken: canvasToken,
                        tool: tool,
                        color: pencil.color,
                        width: pencil.width,
                        logicalCanvasSize: logical,
                        onDrawingChanged: { drawing in
                            localDrawing = drawing
                            scheduleAutosave(drawing: drawing)
                        },
                        onUndoManagerChanged: { manager in
                            canvasUndoManager = manager
                        }
                    )
                    .frame(width: logical.width, height: logical.height)
                    .scaleEffect(fitted.scale, anchor: .center)
                    .frame(width: fitted.size.width, height: fitted.size.height)
                    .clipped()
                    .shadow(radius: 4, y: 2)
                }
            }
        }
    }

    private var toolbar: some View {
        HStack(spacing: 10) {
            Text(bridge.currentOperation == "insert" ? "INSERT" : "UPDATE")
                .font(.caption.bold())

            Text(bridge.selectedPath?.split(separator: "/").last.map(String.init) ?? "graphic")
                .font(.headline)
                .lineLimit(1)

            Divider().frame(height: 26)

            toolButton(.pencil, systemImage: "pencil")
            toolButton(.eraser, systemImage: "eraser")

            ColorPicker("Pencil color", selection: $pencil.color, supportsOpacity: false)
                .labelsHidden()
                .frame(width: 34)

            Slider(value: $pencil.width, in: 1...24, step: 0.5)
                .frame(maxWidth: 190)

            Button {
                canvasUndoManager?.undo()
            } label: {
                Image(systemName: "arrow.uturn.backward")
            }
            .disabled(!(canvasUndoManager?.canUndo ?? false))

            Button {
                canvasUndoManager?.redo()
            } label: {
                Image(systemName: "arrow.uturn.forward")
            }
            .disabled(!(canvasUndoManager?.canRedo ?? false))

            Button(role: .destructive) {
                localDrawing = PKDrawing()
                canvasToken += 1
                scheduleAutosave(drawing: localDrawing, immediate: true)
            } label: {
                Image(systemName: "trash")
            }

            Spacer(minLength: 8)

            Text(bridge.status)
                .font(.caption)
                .foregroundStyle(.secondary)
                .lineLimit(1)

            Button("Disconnect") {
                bridge.disconnect()
            }
            .buttonStyle(.bordered)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(.bar)
    }

    @ViewBuilder
    private func toolButton(_ nextTool: GraphicTool, systemImage: String) -> some View {
        Button {
            tool = nextTool
        } label: {
            Image(systemName: systemImage)
                .frame(width: 34, height: 34)
                .background(tool == nextTool ? Color.accentColor.opacity(0.16) : .clear)
                .clipShape(RoundedRectangle(cornerRadius: 8))
        }
    }

    private func scheduleAutosave(drawing: PKDrawing, immediate: Bool = false) {
        saveTask?.cancel()
        saveTask = Task { @MainActor in
            if !immediate {
                try? await Task.sleep(nanoseconds: 200_000_000)
            }
            guard !Task.isCancelled else { return }
            bridge.save(
                drawing: drawing,
                logicalCanvasSize: logicalCanvasSize,
                pencil: pencil
            )
        }
    }

    private var logicalCanvasSize: CGSize {
        CGSize(
            width: CGFloat(bridge.document?.canvasWidth ?? 1600),
            height: CGFloat(bridge.document?.canvasHeight ?? 1000)
        )
    }

    private func fittedCanvas(
        logical: CGSize,
        available: CGSize
    ) -> (size: CGSize, scale: CGFloat) {
        let availableWidth = max(available.width - 20, 1)
        let availableHeight = max(available.height - 20, 1)
        let widthScale = availableWidth / max(logical.width, 1)
        let heightScale = availableHeight / max(logical.height, 1)
        let scale = min(widthScale, heightScale)
        return (
            CGSize(width: logical.width * scale, height: logical.height * scale),
            scale
        )
    }
}
