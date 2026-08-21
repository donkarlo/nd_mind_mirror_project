import PencilKit
import PhotosUI
import SwiftUI
import UIKit

struct ContentView: View {
    @StateObject private var bridge = GraphicBridgeClient()
    @State private var tool: GraphicTool = .pencil
    @State private var pencil = PencilSettings()
    @StateObject private var recentColors = RecentPencilColors()
    @State private var localDrawing = PKDrawing()
    @State private var backgroundImage: UIImage?
    @State private var selectedPhotoItem: PhotosPickerItem?
    @State private var localToken = -1
    @State private var canvasToken = 0
    @State private var canvasWidth: Double = 1600
    @State private var canvasHeight: Double = 1000
    @State private var canvasWidthText = "1600"
    @State private var canvasHeightText = "1000"
    @State private var showCanvasSizeEditor = false
    @State private var saveTask: Task<Void, Never>?
    @State private var canvasUndoManager: UndoManager?
    @State private var showDiagnostics = true

    var body: some View {
        VStack(spacing: 0) {
            startupBanner
            if bridge.selectedPath != nil {
                drawingScreen
            } else if bridge.isConnected {
                waitingScreen
            } else {
                connectionScreen
            }
        }
        .background(Color(uiColor: .systemGroupedBackground))
        .popover(isPresented: $showCanvasSizeEditor) {
            canvasSizeEditor
                .frame(minWidth: 420, minHeight: 330)
        }
        .onChange(of: bridge.documentToken) { _, token in
            guard token != localToken else { return }
            localToken = token
            localDrawing = bridge.drawing
            backgroundImage = GraphicDocumentStore.backgroundImage(from: bridge.document)
            if let width = bridge.document?.canvasWidth, width > 0 {
                canvasWidth = Double(width)
                canvasWidthText = String(width)
            }
            if let height = bridge.document?.canvasHeight, height > 0 {
                canvasHeight = Double(height)
                canvasHeightText = String(height)
            }
            canvasToken += 1
            if let remotePencil = bridge.document?.pencil {
                if let width = remotePencil.width { pencil.width = width }
                if let color = remotePencil.color { pencil.color = Color(hex: color) }
            }
        }
    }

    private var startupBanner: some View {
        HStack(spacing: 8) {
            Image(systemName: "pencil.and.scribble")
            Text("ND Graphic v0.30.10")
                .font(.subheadline.bold())
            Spacer()
            Text(bridge.isConnected ? "Connected" : "Not connected")
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 7)
        .background(.thinMaterial)
    }

    private var connectionScreen: some View {
        ScrollView {
            VStack(spacing: 18) {
                Text("Connect to Mind Mirror")
                    .font(.largeTitle.bold())
                Text("The Ubuntu bridge must be running. This build listens on iPad TCP port 8768 and Ubuntu connects to it automatically.")
                    .multilineTextAlignment(.center)
                    .foregroundStyle(.secondary)
                VStack(alignment: .leading, spacing: 12) {
                    HStack {
                        Text("iPad listener").font(.headline)
                        Spacer()
                        Text("TCP 8768").font(.system(.body, design: .monospaced))
                    }
                    SecureField("Token (optional)", text: $bridge.token)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .textFieldStyle(.roundedBorder)
                    Button {
                        bridge.connect()
                    } label: {
                        Text("Start listening for Ubuntu").frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                }
                .padding(18)
                .background(.background, in: RoundedRectangle(cornerRadius: 16))

                Text(bridge.status)
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .textSelection(.enabled)

                VStack(alignment: .leading, spacing: 10) {
                    HStack {
                        Button("Run diagnostics") { bridge.runDiagnostics(); showDiagnostics = true }
                        Button("Copy log") { UIPasteboard.general.string = bridge.copyableDiagnostics() }
                        if let logURL = bridge.diagnosticFileURL {
                            ShareLink(item: logURL) { Label("Share log", systemImage: "square.and.arrow.up") }
                        }
                        Button(showDiagnostics ? "Hide log" : "Show log") { showDiagnostics.toggle() }
                    }
                    .buttonStyle(.bordered)
                    if showDiagnostics {
                        ScrollView {
                            Text(bridge.diagnostics.isEmpty ? "No diagnostics yet." : bridge.diagnostics)
                                .font(.system(.caption, design: .monospaced))
                                .textSelection(.enabled)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(10)
                        }
                        .frame(minHeight: 160, maxHeight: 300)
                        .background(Color(uiColor: .secondarySystemBackground), in: RoundedRectangle(cornerRadius: 10))
                    }
                }
                .frame(maxWidth: 760)
            }
            .frame(maxWidth: 650)
            .padding(28)
            .frame(maxWidth: .infinity)
        }
    }

    private var waitingScreen: some View {
        VStack(spacing: 16) {
            Spacer()
            Image(systemName: "ipad.and.arrow.forward").font(.system(size: 52))
            Text("Connected").font(.largeTitle.bold())
            Text("Waiting for Insert / Update from Mind Mirror").font(.title3)
            Text(bridge.status).font(.caption).foregroundStyle(.secondary)
            Button("Disconnect") { bridge.disconnect() }.buttonStyle(.bordered)
            Spacer()
        }
        .padding(28)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var drawingScreen: some View {
        VStack(spacing: 0) {
            toolbar
            PencilCanvasView(
                drawing: localDrawing,
                backgroundImage: backgroundImage,
                documentToken: canvasToken,
                documentIdentifier: bridge.selectedPath ?? "",
                tool: tool,
                color: pencil.color,
                width: pencil.width,
                logicalCanvasSize: logicalCanvasSize,
                onDrawingChanged: { drawing in
                    localDrawing = drawing
                    scheduleAutosave(drawing: drawing)
                },
                onUndoManagerChanged: { manager in canvasUndoManager = manager }
            )
            .clipped()
        }
    }

    private var toolbar: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 6) {
                Text(bridge.currentOperation == "insert" ? "IN" : "UP")
                    .font(.caption2.bold())
                    .padding(.horizontal, 6)
                    .padding(.vertical, 4)
                    .background(Color.accentColor.opacity(0.12), in: Capsule())

                Picker("Tool", selection: $tool) {
                    Image(systemName: "pencil").tag(GraphicTool.pencil)
                    Image(systemName: "highlighter").tag(GraphicTool.highlighter)
                    Image(systemName: "eraser").tag(GraphicTool.eraser)
                }
                .pickerStyle(.segmented)
                .frame(width: 138)
                .accessibilityLabel("Drawing tool")

                ColorPicker("Color", selection: $pencil.color, supportsOpacity: false)
                    .labelsHidden()
                    .frame(width: 30)

                recentColorStrip

                Slider(value: $pencil.width, in: 1...24, step: 0.5)
                    .frame(width: 104)

                PhotosPicker(selection: $selectedPhotoItem, matching: .images) {
                    Image(systemName: "photo.badge.plus")
                        .frame(width: 28, height: 28)
                }
                .buttonStyle(.bordered)
                .onChange(of: selectedPhotoItem) { _, item in importPhoto(item) }

                Button { canvasUndoManager?.undo() } label: { Image(systemName: "arrow.uturn.backward") }
                    .disabled(!(canvasUndoManager?.canUndo ?? false))
                Button { canvasUndoManager?.redo() } label: { Image(systemName: "arrow.uturn.forward") }
                    .disabled(!(canvasUndoManager?.canRedo ?? false))

                Menu {
                    Button("A4 portrait — 1240 × 1754") { setCanvasSize(width: 1240, height: 1754) }
                    Button("A4 landscape — 1754 × 1240") { setCanvasSize(width: 1754, height: 1240) }
                    Button("Square — 1600 × 1600") { setCanvasSize(width: 1600, height: 1600) }
                    Button("Widescreen — 1920 × 1080") { setCanvasSize(width: 1920, height: 1080) }
                    Button("Custom canvas size…") {
                        canvasWidthText = String(Int(canvasWidth))
                        canvasHeightText = String(Int(canvasHeight))
                        showCanvasSizeEditor = true
                    }
                    Divider()
                    if backgroundImage != nil {
                        Button("Remove background photo", role: .destructive) {
                            backgroundImage = nil
                            bridge.save(
                                drawing: localDrawing,
                                backgroundImage: nil,
                                logicalCanvasSize: logicalCanvasSize,
                                pencil: pencil,
                                persistBackground: true
                            )
                        }
                    }
                    Button("Clear drawing", role: .destructive) {
                        localDrawing = PKDrawing()
                        canvasToken += 1
                        scheduleAutosave(drawing: localDrawing, immediate: true)
                    }
                    Divider()
                    Button("Disconnect", role: .destructive) { bridge.disconnect() }
                } label: {
                    Image(systemName: "ellipsis.circle").frame(width: 28, height: 28)
                }

                Text("\(Int(canvasWidth))×\(Int(canvasHeight))")
                    .font(.caption2.monospacedDigit())
                    .foregroundStyle(.secondary)
            }
            .controlSize(.small)
            .padding(.horizontal, 8)
            .padding(.vertical, 5)
        }
        .background(.bar)
    }

    private var recentColorStrip: some View {
        HStack(spacing: 4) {
            ForEach(Array(recentColors.hexColors.prefix(10)), id: \.self) { hex in
                let swatch = Color(hex: hex)
                Button {
                    pencil.color = swatch
                    recentColors.remember(hex: hex)
                } label: {
                    Circle()
                        .fill(swatch)
                        .frame(width: 19, height: 19)
                        .overlay {
                            Circle().stroke(
                                pencil.color.hexRGB().caseInsensitiveCompare(hex) == .orderedSame
                                    ? Color.primary : Color.secondary.opacity(0.25),
                                lineWidth: pencil.color.hexRGB().caseInsensitiveCompare(hex) == .orderedSame ? 2 : 0.7
                            )
                        }
                }
                .buttonStyle(.plain)
            }
        }
        .frame(width: 214, alignment: .leading)
    }

    @ViewBuilder
    private func toolButton(_ nextTool: GraphicTool, systemImage: String) -> some View {
        Button { tool = nextTool } label: {
            Image(systemName: systemImage)
                .frame(width: 28, height: 28)
                .background(tool == nextTool ? Color.accentColor.opacity(0.16) : .clear)
                .clipShape(RoundedRectangle(cornerRadius: 7))
        }
        .buttonStyle(.plain)
    }

    private var canvasSizeEditor: some View {
        NavigationStack {
            Form {
                Section("Canvas size in pixels") {
                    TextField("Width", text: $canvasWidthText).keyboardType(.numberPad)
                    TextField("Height", text: $canvasHeightText).keyboardType(.numberPad)
                }
            }
            .navigationTitle("Canvas Size")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { showCanvasSizeEditor = false }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Apply") {
                        let width = Double(canvasWidthText) ?? canvasWidth
                        let height = Double(canvasHeightText) ?? canvasHeight
                        setCanvasSize(width: width, height: height)
                        showCanvasSizeEditor = false
                    }
                }
            }
        }
        .presentationDetents([.medium])
    }

    private func scheduleAutosave(drawing: PKDrawing, immediate: Bool = false) {
        saveTask?.cancel()
        let pencilUsedForThisDrawing = pencil
        saveTask = Task { @MainActor in
            if !immediate { try? await Task.sleep(nanoseconds: 55_000_000) }
            guard !Task.isCancelled else { return }
            recentColors.remember(pencilUsedForThisDrawing.color)
            bridge.save(
                drawing: drawing,
                backgroundImage: backgroundImage,
                logicalCanvasSize: logicalCanvasSize,
                pencil: pencilUsedForThisDrawing
            )
        }
    }

    private var logicalCanvasSize: CGSize {
        CGSize(width: CGFloat(max(canvasWidth, 64)), height: CGFloat(max(canvasHeight, 64)))
    }

    private func setCanvasSize(width: Double, height: Double) {
        canvasWidth = min(max(width.rounded(), 64), 8192)
        canvasHeight = min(max(height.rounded(), 64), 8192)
        canvasWidthText = String(Int(canvasWidth))
        canvasHeightText = String(Int(canvasHeight))
        canvasToken += 1
        bridge.save(
            drawing: localDrawing,
            backgroundImage: backgroundImage,
            logicalCanvasSize: logicalCanvasSize,
            pencil: pencil
        )
    }

    private func importPhoto(_ item: PhotosPickerItem?) {
        guard let item else { return }
        Task {
            guard let data = try? await item.loadTransferable(type: Data.self),
                  let image = UIImage(data: data) else {
                await MainActor.run { bridge.status = "Could not load the selected photo" }
                return
            }
            await MainActor.run {
                backgroundImage = image
                selectedPhotoItem = nil
                bridge.save(
                    drawing: localDrawing,
                    backgroundImage: image,
                    logicalCanvasSize: logicalCanvasSize,
                    pencil: pencil,
                    persistBackground: true
                )
            }
        }
    }
}
