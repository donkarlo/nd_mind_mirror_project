// Builds the native iPad drawing workflow, including persistent stroke settings, zoom status, recent colors, and lasso selection.

import Foundation
import PencilKit
import PhotosUI
import SwiftUI
import UIKit

/// Presents connection, drawing, tool, palette, canvas, selection, and save controls for ND Graphic on iPad.
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
    @State private var zoomScale: CGFloat = 1.0
    @State private var showCanvasSizeEditor = false
    @State private var showRecentColors = false
    @State private var saveTask: Task<Void, Never>?
    @State private var canvasUndoManager: UndoManager?
    @State private var showDiagnostics = true

    /// Selects the connection, waiting, or drawing screen for the current bridge state.
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
                if let color = remotePencil.color {
                    pencil.color = Color(hex: color)
                    recentColors.remember(hex: color, for: tool)
                }
            }
        }
        .onChange(of: tool) { oldTool, newTool in
            switchToolColor(from: oldTool, to: newTool)
            if !newTool.supportsColor {
                showRecentColors = false
            }
        }
    }

    /// Shows the compact application/version and bridge connection banner.
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

    /// Shows bridge startup, token, status, and diagnostic controls before a connection exists.
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

    /// Shows the connected idle screen while Ubuntu has not selected a graphic document yet.
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

    /// Shows the active toolbar, optional color matrix, canvas status, and PencilKit drawing surface.
    private var drawingScreen: some View {
        VStack(spacing: 0) {
            toolbar
            if showRecentColors && tool.supportsColor {
                recentColorGrid
            }
            canvasStatusBar
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
                onUndoManagerChanged: { manager in canvasUndoManager = manager },
                onZoomChanged: { scale in zoomScale = scale }
            )
            .clipped()
        }
    }

    /// Builds the horizontal drawing toolbar with compact stroke controls and a palette-grid toggle.
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
                    Image(systemName: "lasso").tag(GraphicTool.lasso)
                }
                .pickerStyle(.segmented)
                .frame(width: 184)
                .accessibilityLabel("Drawing tool")

                if tool.supportsColor {
                    ColorPicker("Color", selection: toolColorBinding, supportsOpacity: false)
                        .labelsHidden()
                        .frame(width: 30)
                    Button {
                        showRecentColors.toggle()
                    } label: {
                        Image(systemName: showRecentColors ? "circle.grid.3x3.fill" : "circle.grid.3x3")
                            .frame(width: 28, height: 28)
                    }
                    .buttonStyle(.bordered)
                    .accessibilityLabel("Recent colors")
                }

                if tool.supportsWidth {
                    CompactThicknessSlider(value: $pencil.width, range: 1...24, step: 0.5)
                        .frame(width: 108, height: 24)
                    Text(String(format: "%.1f", pencil.width))
                        .font(.caption2.monospacedDigit())
                        .frame(minWidth: 30, alignment: .trailing)
                }

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
            }
            .controlSize(.small)
            .padding(.horizontal, 8)
            .padding(.vertical, 5)
        }
        .background(.bar)
    }

    /// Shows the current absolute zoom percentage and logical canvas size at all times while drawing.
    private var canvasStatusBar: some View {
        HStack(spacing: 14) {
            Label("\(Int((zoomScale * 100).rounded()))%", systemImage: "magnifyingglass")
            Text("Canvas \(Int(canvasWidth)) × \(Int(canvasHeight)) px")
            if tool == .lasso {
                Text("Lasso: draw around strokes, then drag the selection")
                    .foregroundStyle(.secondary)
            }
            Spacer()
        }
        .font(.caption2.monospacedDigit())
        .padding(.horizontal, 10)
        .padding(.vertical, 4)
        .background(Color(uiColor: .secondarySystemBackground))
    }

    /// Binds the color picker to the current tool and records its choice only in that tool's history.
    private var toolColorBinding: Binding<Color> {
        Binding(
            get: { pencil.color },
            set: { newColor in
                pencil.color = newColor
                recentColors.remember(newColor, for: tool)
            }
        )
    }

    /// Displays ten recent/default colors below the toolbar in a compact five-by-two matrix.
    private var recentColorGrid: some View {
        let colors = recentColors.matrixHexColors(for: tool)
        let columns = Array(repeating: GridItem(.fixed(32), spacing: 6), count: 5)
        return HStack(alignment: .top, spacing: 10) {
            Text("Recent colors")
                .font(.caption.bold())
                .padding(.top, 8)
            LazyVGrid(columns: columns, alignment: .leading, spacing: 6) {
                ForEach(colors, id: \.self) { hex in
                    let swatch = Color(hex: hex)
                    Button {
                        pencil.color = swatch
                        recentColors.remember(hex: hex, for: tool)
                    } label: {
                        RoundedRectangle(cornerRadius: 6)
                            .fill(swatch)
                            .frame(width: 30, height: 30)
                            .overlay {
                                RoundedRectangle(cornerRadius: 6).stroke(
                                    pencil.color.hexRGB().caseInsensitiveCompare(hex) == .orderedSame
                                        ? Color.primary : Color.secondary.opacity(0.25),
                                    lineWidth: pencil.color.hexRGB().caseInsensitiveCompare(hex) == .orderedSame ? 2 : 0.7
                                )
                            }
                    }
                    .buttonStyle(.plain)
                }
            }
            Spacer()
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(.bar)
    }

    /// Builds an individual tool-selection button for compact toolbar variants.
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

    /// Shows the custom canvas-size form and applies validated dimensions on confirmation.
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

    /// Switches from one drawing tool's color memory to the newly selected tool's own preferred color.
    private func switchToolColor(from oldTool: GraphicTool, to newTool: GraphicTool) {
        if oldTool.supportsColor {
            recentColors.remember(pencil.color, for: oldTool)
        }
        guard newTool.supportsColor else { return }
        let preferred = recentColors.preferredHex(for: newTool, fallback: pencil.color.hexRGB())
        pencil.color = Color(hex: preferred)
    }

    /// Debounces drawing saves and records the stroke color under the tool that actually produced the drawing.
    private func scheduleAutosave(drawing: PKDrawing, immediate: Bool = false) {
        saveTask?.cancel()
        let pencilUsedForThisDrawing = pencil
        let toolUsedForThisDrawing = tool
        saveTask = Task { @MainActor in
            if !immediate { try? await Task.sleep(nanoseconds: 55_000_000) }
            guard !Task.isCancelled else { return }
            recentColors.remember(pencilUsedForThisDrawing.color, for: toolUsedForThisDrawing)
            bridge.save(
                drawing: drawing,
                backgroundImage: backgroundImage,
                logicalCanvasSize: logicalCanvasSize,
                pencil: pencilUsedForThisDrawing
            )
        }
    }

    /// Returns the clamped logical canvas size used for rendering and persistence.
    private var logicalCanvasSize: CGSize {
        CGSize(width: CGFloat(max(canvasWidth, 64)), height: CGFloat(max(canvasHeight, 64)))
    }

    /// Applies a bounded canvas size, refreshes the canvas token, and saves the document.
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

    /// Loads a selected Photos image as the canvas background and persists it through the bridge.
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
