import Foundation
import PencilKit
import PhotosUI
import SwiftUI
import UIKit

/// Main iPad drawing screen with one atomic drawing+raster history.
struct ContentView: View {
    @StateObject private var bridge = GraphicBridgeClient()
    @StateObject private var activeTool = ActiveDrawingToolController()
    @StateObject private var savedTools = SavedDrawingToolStore()
    @StateObject private var recentColors = RecentPencilColors()
    @StateObject private var editHistory = CanvasEditHistoryController(maximumDepth: 200)
    @StateObject private var saveGate = GraphicDocumentSaveGate()

    @AppStorage("graphic.last.canvas.width") private var rememberedCanvasWidth: Double = 1240
    @AppStorage("graphic.last.canvas.height") private var rememberedCanvasHeight: Double = 1754
    @AppStorage("graphic.measurement.grid.visible") private var showMeasurementGrid = true
    @AppStorage("graphic.measurement.rulers.visible") private var showMeasurementRulers = true

    private let rasterComposer = RasterCanvasComposer()

    @State private var localDrawing = PKDrawing()
    @State private var backgroundImage: UIImage?
    @State private var localToken = -1
    @State private var canvasToken = 0
    @State private var canvasWidth: Double = 1240
    @State private var canvasHeight: Double = 1754
    @State private var zoomScale: CGFloat = 1
    @State private var zoom100RequestToken = 0
    @State private var selectedPhotoItem: PhotosPickerItem?
    @State private var showCanvasEditor = false
    @State private var canvasWidthText = "1240"
    @State private var canvasHeightText = "1754"
    @State private var loadedPath: String?
    @State private var lastLocalEdit = Date.distantPast
    @State private var initializedTool = false
    @State private var pendingRemoteToken: Int?

    var body: some View {
        VStack(spacing: 0) {
            header
            if bridge.selectedPath == nil { connectionScreen } else { drawingScreen }
        }
        .popover(isPresented: $showCanvasEditor) {
            CanvasSizeEditorView(
                widthText: $canvasWidthText,
                heightText: $canvasHeightText,
                onApply: applyCanvasDraft,
                onCancel: { showCanvasEditor = false }
            )
        }
        .onAppear {
            if !initializedTool {
                initializedTool = true
                activeTool.reconcileSavedToolSelection(savedTools.tools)
            }
            bindToolRuntime()
        }
        .onChange(of: bridge.documentToken) { _, token in loadRemoteDocument(token: token) }
        .onChange(of: activeTool.state) { _, _ in bindToolRuntime() }
        .onChange(of: savedTools.tools) { _, tools in
            activeTool.reconcileSavedToolSelection(tools)
        }
        .onChange(of: activeTool.isPencilGestureActive) { _, active in
            if !active { consumePendingRemoteDocument() }
        }
    }

    private var header: some View {
        HStack {
            Text(graphicContextTitle)
                .font(.subheadline.bold())
                .lineLimit(1)
                .truncationMode(.middle)
            Spacer()
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 7)
        .background(.thinMaterial)
    }

    private var connectionScreen: some View {
        VStack(spacing: 16) {
            Spacer()
            if bridge.isConnected {
                Text("No image selected").font(.largeTitle.bold())
                Text("On Ubuntu, right-click an image and choose Edit image in iPad.")
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                Button("Disconnect") { bridge.disconnect() }
                    .buttonStyle(.bordered)
            } else {
                Text("Connect to Mind Mirror").font(.largeTitle.bold())
                Text("iPad listens on TCP 8768; Ubuntu connects automatically.")
                    .foregroundStyle(.secondary)
                SecureField("Token (optional)", text: $bridge.token)
                    .textFieldStyle(.roundedBorder)
                    .frame(maxWidth: 480)
                Button("Start listening for Ubuntu") { bridge.connect() }
                    .buttonStyle(.borderedProminent)
            }
            Text(bridge.status).font(.caption).foregroundStyle(.secondary)
            Spacer()
        }
        .padding(24)
    }

    private var drawingScreen: some View {
        VStack(spacing: 0) {
            DrawingToolbarView(
                activeTool: activeTool,
                savedTools: savedTools,
                recentColors: recentColors,
                editHistory: editHistory,
                showMeasurementGrid: $showMeasurementGrid,
                showMeasurementRulers: $showMeasurementRulers,
                selectedPhotoItem: $selectedPhotoItem,
                onUndo: performUndo,
                onRedo: performRedo,
                onZoom100: { zoom100RequestToken += 1 },
                onSetCanvas: setCanvas,
                onCustomCanvas: openCanvasEditor,
                onClearDrawing: clearDrawing,
                onDisconnect: bridge.disconnect
            )
            .onChange(of: selectedPhotoItem) { _, item in importPhoto(item) }

            statusBar
            MeasurementRulerFrameView(
                isVisible: showMeasurementRulers,
                zoomScale: zoomScale
            ) {
                PencilCanvasView(
                    drawing: localDrawing,
                    backgroundImage: backgroundImage,
                    activeToolController: activeTool,
                    documentToken: canvasToken,
                    documentIdentifier: bridge.selectedPath ?? "",
                    tool: activeTool.kind,
                    imageObjects: [],
                    selectedImageObjectID: nil,
                    logicalCanvasSize: logicalCanvasSize,
                    showMeasurementGrid: showMeasurementGrid,
                    showMeasurementRulers: false,
                    zoom100RequestToken: zoom100RequestToken,
                    onDrawingChanged: handleDrawingChanged,
                    onUndoManagerChanged: { _ in },
                    onZoomChanged: { zoomScale = $0 },
                    onImageObjectSelectionChanged: { _ in },
                    onImageObjectsCommitted: { _, _, _ in }
                )
                .clipped()
                .onAppear { bindToolRuntime() }
            }
        }
    }

    private var statusBar: some View {
        HStack(spacing: 12) {
            Text(activeToolName).font(.caption2.bold()).foregroundStyle(Color.accentColor)
            Text("\(Int((zoomScale * 100).rounded()))%")
                .font(.caption2.monospacedDigit())
            Text("\(Int(canvasWidth)) × \(Int(canvasHeight))")
                .font(.caption2.monospacedDigit())
            Spacer()
            if activeTool.kind == .eraser {
                Text("\(activeTool.eraserMode.title) • \(Int(activeTool.width)) px")
                    .font(.caption2).foregroundStyle(.secondary)
            }
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 4)
        .background(Color(uiColor: .secondarySystemBackground))
    }

    private func loadRemoteDocument(token: Int) {
        guard token != localToken else { return }
        if activeTool.isCanvasGestureInFlight {
            pendingRemoteToken = token
            return
        }
        localToken = token
        guard let path = bridge.selectedPath else {
            loadedPath = nil
            saveGate.reset()
            return
        }

        saveGate.beginLoading(path: path)
        let newDocument = path != loadedPath
        loadedPath = path
        localDrawing = bridge.drawing
        if bridge.currentOperation == "insert" {
            canvasWidth = max(rememberedCanvasWidth, 64)
            canvasHeight = max(rememberedCanvasHeight, 64)
        } else {
            if let width = bridge.document?.canvasWidth, width > 0 { canvasWidth = Double(width) }
            if let height = bridge.document?.canvasHeight, height > 0 { canvasHeight = Double(height) }
        }
        if !showCanvasEditor {
            canvasWidthText = String(Int(canvasWidth))
            canvasHeightText = String(Int(canvasHeight))
        }
        rememberedCanvasWidth = canvasWidth
        rememberedCanvasHeight = canvasHeight

        let legacyObjects = bridge.document?.imageObjects ?? []
        backgroundImage = rasterComposer.flatten(
            backgroundImage: bridge.backgroundImageForCurrentDocument(),
            legacyImageObjects: legacyObjects,
            canvasSize: logicalCanvasSize
        )
        CanvasImageObjectStore.clear(documentIdentifier: path)
        editHistory.reset(drawing: localDrawing, backgroundImage: backgroundImage)
        if let remote = bridge.document?.pencil {
            activeTool.adoptDocumentPencil(width: remote.width, colorHex: remote.color)
        }
        canvasToken += 1
        if newDocument { zoom100RequestToken += 1 }
        saveGate.finishLoading(
            path: path,
            operation: bridge.currentOperation,
            drawing: localDrawing,
            backgroundImage: backgroundImage,
            hasImageObjects: !legacyObjects.isEmpty
        )
        bindToolRuntime()
    }

    private func bindToolRuntime() {
        activeTool.bindRuntime(
            canvasSize: logicalCanvasSize,
            historyController: editHistory,
            canvasStateCommitted: { drawing, image, rasterChanged in
                lastLocalEdit = Date()
                localDrawing = drawing
                backgroundImage = image
                save(
                    drawing: drawing,
                    backgroundImage: image,
                    persistBackground: rasterChanged
                )
            },
            undoRequested: performUndo
        )
    }

    private func handleDrawingChanged(_ drawing: PKDrawing) {
        lastLocalEdit = Date()
        localDrawing = drawing
        if activeTool.consumeProgrammaticDrawingChange(drawing) { return }
        guard !activeTool.isCanvasGestureInFlight else { return }
        if editHistory.record(drawing: drawing, backgroundImage: backgroundImage) {
            saveCurrentState(persistBackground: false)
        }
    }

    private func performUndo() {
        guard !activeTool.isPencilGestureActive,
              let snapshot = editHistory.undo() else { return }
        restore(snapshot)
    }

    private func performRedo() {
        guard !activeTool.isPencilGestureActive,
              let snapshot = editHistory.redo() else { return }
        restore(snapshot)
    }

    private func restore(_ snapshot: CanvasEditHistoryController.Snapshot) {
        lastLocalEdit = Date()
        activeTool.applyHistorySnapshot(snapshot)
        localDrawing = snapshot.drawing
        backgroundImage = snapshot.backgroundImage
        // Force SwiftUI/PencilCanvasView to reconcile with the restored snapshot.
        // Without a new document token, a later local edit can be applied on top
        // of an older view state and visually resurrect an undone stroke.
        canvasToken += 1
        saveCurrentState(persistBackground: true)
    }

    private func clearDrawing() {
        guard !activeTool.isPencilGestureActive else { return }
        let cleared = PKDrawing()
        guard editHistory.record(
            drawing: cleared,
            backgroundImage: backgroundImage
        ) else { return }
        lastLocalEdit = Date()
        localDrawing = cleared
        canvasToken += 1
        saveCurrentState(persistBackground: false)
    }

    private func saveCurrentState(persistBackground: Bool) {
        save(
            drawing: localDrawing,
            backgroundImage: backgroundImage,
            persistBackground: persistBackground
        )
    }

    private func save(
        drawing: PKDrawing,
        backgroundImage: UIImage?,
        persistBackground: Bool
    ) {
        guard saveGate.allowsSave(path: bridge.selectedPath) else { return }
        bridge.save(
            drawing: drawing,
            backgroundImage: backgroundImage,
            logicalCanvasSize: logicalCanvasSize,
            pencil: activeTool.pencilSettings,
            persistBackground: persistBackground
        )
    }

    private func consumePendingRemoteDocument() {
        guard let token = pendingRemoteToken else { return }
        pendingRemoteToken = nil
        if bridge.selectedPath != loadedPath { loadRemoteDocument(token: token) }
    }

    private func openCanvasEditor() {
        canvasWidthText = String(Int(canvasWidth))
        canvasHeightText = String(Int(canvasHeight))
        showCanvasEditor = true
    }

    private func applyCanvasDraft() {
        setCanvas(
            width: Double(canvasWidthText) ?? canvasWidth,
            height: Double(canvasHeightText) ?? canvasHeight
        )
        showCanvasEditor = false
    }

    private func setCanvas(width: Double, height: Double) {
        canvasWidth = max(width.rounded(), 64)
        canvasHeight = max(height.rounded(), 64)
        rememberedCanvasWidth = canvasWidth
        rememberedCanvasHeight = canvasHeight
        canvasWidthText = String(Int(canvasWidth))
        canvasHeightText = String(Int(canvasHeight))
        if saveGate.allowsSave(path: bridge.selectedPath) {
            bridge.saveCanvasSize(logicalCanvasSize: logicalCanvasSize)
        }
        editHistory.reset(drawing: localDrawing, backgroundImage: backgroundImage)
        bindToolRuntime()
    }

    private func importPhoto(_ item: PhotosPickerItem?) {
        guard let item else { return }
        Task {
            guard let data = try? await item.loadTransferable(type: Data.self),
                  let image = UIImage(data: data) else { return }
            await MainActor.run {
                selectedPhotoItem = nil
                guard let merged = rasterComposer.inserting(
                    image: image,
                    into: backgroundImage,
                    canvasSize: logicalCanvasSize
                ), editHistory.record(
                    drawing: localDrawing,
                    backgroundImage: merged
                ) else { return }
                backgroundImage = merged
                lastLocalEdit = Date()
                saveCurrentState(persistBackground: true)
            }
        }
    }

    private var logicalCanvasSize: CGSize {
        CGSize(
            width: CGFloat(max(canvasWidth, 64)),
            height: CGFloat(max(canvasHeight, 64))
        )
    }

    private var graphicContextTitle: String {
        guard let selectedPath = bridge.selectedPath else { return "ND Graphic" }
        let sidecarURL = URL(fileURLWithPath: selectedPath)
        let folder = sidecarURL.deletingLastPathComponent().lastPathComponent
        let imageName = bridge.document?.imageName?.trimmingCharacters(in: .whitespacesAndNewlines)
        let resolved = imageName?.isEmpty == false
            ? imageName!
            : sidecarURL.deletingPathExtension().lastPathComponent + ".png"
        return folder.isEmpty ? resolved : "\(folder) / \(resolved)"
    }

    private var activeToolName: String {
        switch activeTool.kind {
        case .pencil:
            return "Pencil \(activeTool.width.formatted(.number.precision(.fractionLength(0...1)))) px"
        case .highlighter:
            return "Marker \(activeTool.width.formatted(.number.precision(.fractionLength(0...1)))) px"
        case .eraser:
            return "\(activeTool.eraserMode.title) Eraser \(Int(activeTool.width.rounded())) px"
        case .lasso:
            return "Lasso"
        }
    }
}
