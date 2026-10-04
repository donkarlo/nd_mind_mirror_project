// Main iPad drawing screen. Ubuntu opens the image once; the iPad owns the edit session until close.

import Foundation
import PencilKit
import PhotosUI
import SwiftUI
import UIKit

struct ContentView: View {
    @StateObject private var bridge = GraphicBridgeClient()
    @StateObject private var activeTool = ActiveDrawingToolController()
    @StateObject private var savedTools = SavedDrawingToolStore()
    @StateObject private var recentColors = RecentPencilColors()
    @StateObject private var editHistory = CanvasEditHistoryController(maximumDepth: 200)
    @StateObject private var saveRetryController = GraphicSaveRetryController()
    @StateObject private var saveGate = GraphicDocumentSaveGate()
    @StateObject private var liveSyncSettings = LiveGraphicSyncSettingsStore()
    @StateObject private var pencilContactPreviewSettings = PencilContactPreviewSettingsStore()
    @StateObject private var pencilContactPreviewVisibility = PencilContactPreviewVisibilityController()
    @StateObject private var liveSaveScheduler = LiveGraphicSaveScheduler()
    @StateObject private var documentNavigation = GraphicDocumentNavigationHistory()

    @AppStorage("graphic.last.canvas.width") private var rememberedCanvasWidth: Double = 760
    @AppStorage("graphic.last.canvas.height") private var rememberedCanvasHeight: Double = 980
    @AppStorage("graphic.measurement.grid.visible") private var showMeasurementGrid = true
    @AppStorage("graphic.measurement.rulers.visible") private var showMeasurementRulers = true

    private let rasterComposer = RasterCanvasComposer()

    @State private var localDrawing = PKDrawing()
    @State private var backgroundImage: UIImage?
    @State private var localToken = -1
    @State private var canvasToken = 0
    @State private var canvasWidth: Double = 760
    @State private var canvasHeight: Double = 980
    @State private var zoomScale: CGFloat = 1
    @State private var zoom100RequestToken = 0
    @State private var selectedPhotoItem: PhotosPickerItem?
    @State private var showCanvasEditor = false
    @State private var showLiveSyncSettings = false
    @State private var canvasWidthText = "760"
    @State private var canvasHeightText = "980"
    @State private var loadedPath: String?
    @State private var initializedTool = false
    @State private var pendingRemoteToken: Int?
    @State private var quickToolPaletteAnchor: CGPoint?
    @State private var pencilContactPreviewAnchor: CGPoint?
    @State private var quickPhotoPickerPresented = false

    var body: some View {
        VStack(spacing: 0) {
            header
            if bridge.selectedPath == nil {
                connectionScreen
            } else {
                drawingScreen
            }
        }
        .popover(isPresented: $showCanvasEditor) {
            CanvasSizeEditorView(
                widthText: $canvasWidthText,
                heightText: $canvasHeightText,
                onApply: applyCanvasDraft,
                onCancel: { showCanvasEditor = false }
            )
        }
        .sheet(isPresented: $showLiveSyncSettings) {
            LiveGraphicSyncSettingsView(
                settingsStore: liveSyncSettings,
                pencilContactPreviewSettings: pencilContactPreviewSettings
            )
        }
        .photosPicker(
            isPresented: $quickPhotoPickerPresented,
            selection: $selectedPhotoItem,
            matching: .images
        )
        .onAppear {
            if !initializedTool {
                initializedTool = true
                activeTool.reconcileSavedToolSelection(savedTools.tools)
            }
            bindToolRuntime()
        }
        .onChange(of: bridge.documentToken) { _, token in
            loadRemoteDocument(token: token)
        }
        .onChange(of: bridge.status) { _, status in
            handleBridgeStatus(status)
        }
        .onChange(of: saveRetryController.didExhaustRetries) { _, exhausted in
            if exhausted {
                bridge.status = "Save not confirmed — image kept open"
            }
        }
        .onChange(of: activeTool.state) { _, _ in
            bindToolRuntime()
        }
        .onChange(of: savedTools.tools) { _, tools in
            activeTool.reconcileSavedToolSelection(tools)
        }
        .onChange(of: activeTool.isPencilGestureActive) { _, active in
            if !active {
                consumePendingRemoteDocument()
            }
        }
    }

    private var header: some View {
        HStack {
            Text(graphicContextTitle)
                .font(.subheadline.bold())
                .lineLimit(1)
                .truncationMode(.middle)
            Spacer()

            if bridge.selectedPath != nil {
                Button(action: navigateBack) {
                    Image(systemName: "chevron.left")
                        .font(.title3)
                        .frame(width: 44, height: 44)
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .disabled(!documentNavigation.canGoBack)
                .accessibilityLabel("Previous graphic")

                Button(action: navigateForward) {
                    Image(systemName: "chevron.right")
                        .font(.title3)
                        .frame(width: 44, height: 44)
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .disabled(!documentNavigation.canGoForward)
                .accessibilityLabel("Next graphic")

                HeaderDrawingControlsView(
                    activeTool: activeTool,
                    editHistory: editHistory,
                    showMeasurementRulers: $showMeasurementRulers,
                    showMeasurementGrid: $showMeasurementGrid,
                    onRedo: performRedo,
                    onUndo: performUndo,
                    onZoom100: { zoom100RequestToken += 1 },
                    onSetCanvas: setCanvas,
                    onCustomCanvas: openCanvasEditor,
                    onClearDrawing: clearDrawing,
                    onDisconnect: bridge.disconnect
                )
            }

            Button {
                showLiveSyncSettings = true
            } label: {
                Image(systemName: "gearshape.fill")
                    .font(.title3)
                    .frame(width: 44, height: 44)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .contentShape(Rectangle())
            .accessibilityLabel("Live sync settings")

            if bridge.selectedPath != nil {
                Button(action: closeCurrentImage) {
                    Image(systemName: "xmark.circle.fill")
                        .font(.title3)
                        .frame(width: 44, height: 44)
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .contentShape(Rectangle())
                .accessibilityLabel("Close image")
            }
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 7)
        .background(.thinMaterial)
    }

    private var connectionScreen: some View {
        VStack(spacing: 16) {
            Spacer()
            if bridge.isConnected {
                Text("Waiting for image from Ubuntu")
                    .font(.largeTitle.bold())
                Text("On Ubuntu, right-click an image and choose Edit image in iPad.")
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                Button("Disconnect") {
                    bridge.disconnect()
                }
                .buttonStyle(.bordered)
            } else {
                Text("Connect to Mind Mirror")
                    .font(.largeTitle.bold())
                Text("iPad listens on TCP 8768; Ubuntu connects automatically.")
                    .foregroundStyle(.secondary)
                SecureField("Token (optional)", text: $bridge.token)
                    .textFieldStyle(.roundedBorder)
                    .frame(maxWidth: 480)
                Button("Start listening for Ubuntu") {
                    bridge.connect()
                }
                .buttonStyle(.borderedProminent)
            }
            Text(bridge.status)
                .font(.caption)
                .foregroundStyle(.secondary)
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
                selectedPhotoItem: $selectedPhotoItem
            )
            .onChange(of: selectedPhotoItem) { _, item in
                quickToolPaletteAnchor = nil
                importPhoto(item)
            }

            statusBar
            MeasurementRulerFrameView(
                isVisible: showMeasurementRulers,
                zoomScale: zoomScale
            ) {
                ZStack(alignment: .topLeading) {
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
                        quickToolPalettePresented: quickToolPaletteAnchor != nil,
                        onPencilContactBegan: showPencilContactPreview,
                        onPencilSingleTap: { _ in
                            quickToolPaletteAnchor = nil
                        },
                        onPencilDoubleTap: { point in
                            pencilContactPreviewAnchor = nil
                            quickToolPaletteAnchor = point
                        },
                        onDrawingChanged: handleDrawingChanged,
                        onUndoManagerChanged: { _ in },
                        onZoomChanged: { zoomScale = $0 },
                        onImageObjectSelectionChanged: { _ in },
                        onImageObjectsCommitted: { _, _, _ in }
                    )

                    if let pencilContactPreviewAnchor,
                       quickToolPaletteAnchor == nil {
                        PencilContactToolPreviewView(
                            tool: activeTool.kind,
                            color: activeTool.color,
                            opacity: activeTool.opacity,
                            eraserMode: activeTool.eraserMode,
                            anchor: pencilContactPreviewAnchor
                        )
                    }

                    if let quickToolPaletteAnchor {
                        QuickDrawingToolPaletteView(
                            activeTool: activeTool,
                            savedTools: savedTools,
                            editHistory: editHistory,
                            anchor: quickToolPaletteAnchor,
                            onRedo: performRedo,
                            onUndo: performUndo,
                            onSelectSavedTool: selectQuickTool,
                            onSelectLasso: selectQuickLasso,
                            onAddImage: openQuickPhotoPicker
                        )
                    }
                }
                .clipped()
                .onAppear {
                    bindToolRuntime()
                }
            }
        }
    }

    private var statusBar: some View {
        HStack(spacing: 12) {
            Text(activeToolName)
                .font(.caption2.bold())
                .foregroundStyle(Color.accentColor)
            Text("\(Int((zoomScale * 100).rounded()))%")
                .font(.caption2.monospacedDigit())
            Text("\(Int(canvasWidth)) × \(Int(canvasHeight))")
                .font(.caption2.monospacedDigit())
            Text("Ubuntu \(Int(liveSyncSettings.updateRateHz.rounded()))/s")
                .font(.caption2.monospacedDigit())
                .foregroundStyle(.secondary)
            Spacer()
            if activeTool.kind == .eraser {
                Text("\(activeTool.eraserMode.title) • \(Int(activeTool.width)) px")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 4)
        .background(Color(uiColor: .secondarySystemBackground))
    }

    private func loadRemoteDocument(token: Int) {
        guard token != localToken else { return }
        quickToolPaletteAnchor = nil
        if activeTool.isCanvasGestureInFlight {
            pendingRemoteToken = token
            return
        }

        localToken = token
        liveSaveScheduler.cancelPending()
        saveRetryController.reset()
        guard let path = bridge.selectedPath else {
            loadedPath = nil
            activeTool.prepareForRemoteDocumentLoad()
            saveGate.reset()
            return
        }

        // A desktop rename changes only the document identity/path. Keep the
        // live canvas, raster state, viewport, and Undo/Redo history intact.
        if let renamedFrom = bridge.document?.renamedFrom,
           loadedPath == renamedFrom,
           path != renamedFrom {
            saveGate.remapPath(from: renamedFrom, to: path)
            documentNavigation.remapPath(from: renamedFrom, to: path)
            loadedPath = path
            return
        }

        // Ubuntu owns only the initial open. Once this path is active, the iPad
        // remains authoritative until it is closed, so repeated same-path opens
        // cannot reset Undo history or replace in-progress raster/Pencil edits.
        if path == loadedPath {
            return
        }

        activeTool.prepareForRemoteDocumentLoad()
        pencilContactPreviewVisibility.reset()
        saveGate.beginLoading(path: path)
        let newDocument = path != loadedPath
        loadedPath = path
        documentNavigation.recordOpened(path: path)
        localDrawing = bridge.drawing

        let remoteBackground = bridge.backgroundImageForCurrentDocument()
        if bridge.currentOperation == "insert" {
            if let width = bridge.document?.canvasWidth, width > 0 {
                canvasWidth = Double(width)
            } else {
                canvasWidth = 760
            }
            if let height = bridge.document?.canvasHeight, height > 0 {
                canvasHeight = Double(height)
            } else {
                canvasHeight = 980
            }
        } else {
            if let width = bridge.document?.canvasWidth, width > 0 {
                canvasWidth = Double(width)
            } else if let remoteBackground, remoteBackground.size.width > 0 {
                canvasWidth = Double(remoteBackground.size.width)
            }

            if let height = bridge.document?.canvasHeight, height > 0 {
                canvasHeight = Double(height)
            } else if let remoteBackground, remoteBackground.size.height > 0 {
                canvasHeight = Double(remoteBackground.size.height)
            }
        }

        if !showCanvasEditor {
            canvasWidthText = String(Int(canvasWidth))
            canvasHeightText = String(Int(canvasHeight))
        }
        rememberedCanvasWidth = canvasWidth
        rememberedCanvasHeight = canvasHeight

        let legacyObjects = bridge.document?.imageObjects ?? []
        backgroundImage = rasterComposer.flatten(
            backgroundImage: remoteBackground,
            legacyImageObjects: legacyObjects,
            canvasSize: logicalCanvasSize
        )
        CanvasImageObjectStore.clear(documentIdentifier: path)
        editHistory.reset(
            drawing: localDrawing,
            backgroundImage: backgroundImage
        )

        if let remote = bridge.document?.pencil {
            activeTool.adoptDocumentPencil(
                width: remote.width,
                colorHex: remote.color
            )
        }

        canvasToken += 1
        if newDocument {
            zoom100RequestToken += 1
        }
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
                liveSaveScheduler.cancelPending()
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
        if activeTool.consumeProgrammaticDrawingChange(drawing) {
            return
        }

        pencilContactPreviewVisibility.recordDrawingActivity()
        localDrawing = drawing
        if activeTool.isCanvasGestureInFlight {
            scheduleLiveSave(drawing)
            return
        }

        liveSaveScheduler.cancelPending()
        if editHistory.record(
            drawing: drawing,
            backgroundImage: backgroundImage
        ) {
            saveCurrentState(persistBackground: false)
        }
    }

    private func scheduleLiveSave(_ drawing: PKDrawing) {
        guard saveGate.allowsSave(path: bridge.selectedPath) else { return }

        let canvasSize = logicalCanvasSize
        let pencil = activeTool.pencilSettings
        let image = backgroundImage

        liveSaveScheduler.submit(updateRateHz: liveSyncSettings.updateRateHz) {
            bridge.save(
                drawing: drawing,
                backgroundImage: image,
                logicalCanvasSize: canvasSize,
                pencil: pencil,
                persistBackground: false
            )
        }
    }

    private func performUndo() {
        guard !activeTool.isPencilGestureActive,
              let snapshot = editHistory.undo() else {
            return
        }
        restore(snapshot)
    }

    private func performRedo() {
        guard !activeTool.isPencilGestureActive,
              let snapshot = editHistory.redo() else {
            return
        }
        restore(snapshot)
    }

    private func showPencilContactPreview(_ point: CGPoint) {
        guard quickToolPaletteAnchor == nil,
              pencilContactPreviewVisibility.shouldShow(
                minimumIdleSeconds: pencilContactPreviewSettings.minimumIdleSeconds
              ) else { return }
        pencilContactPreviewAnchor = point
        let previewPoint = point
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.55) {
            if pencilContactPreviewAnchor == previewPoint {
                pencilContactPreviewAnchor = nil
            }
        }
    }

    private func selectQuickTool(_ savedTool: SavedDrawingTool) {
        activeTool.select(savedTool: savedTool)
        if savedTool.kind.supportsColor {
            recentColors.remember(hex: savedTool.colorHex, for: savedTool.kind)
        }
        quickToolPaletteAnchor = nil
    }

    private func selectQuickLasso() {
        activeTool.select(kind: .lasso)
        quickToolPaletteAnchor = nil
    }

    private func openQuickPhotoPicker() {
        quickToolPaletteAnchor = nil
        quickPhotoPickerPresented = true
    }

    private func restore(_ snapshot: CanvasEditHistoryController.Snapshot) {
        liveSaveScheduler.cancelPending()
        activeTool.applyHistorySnapshot(snapshot)
        localDrawing = snapshot.drawing
        backgroundImage = snapshot.backgroundImage
        saveCurrentState(persistBackground: true)
    }

    private func clearDrawing() {
        guard !activeTool.isPencilGestureActive else { return }
        let cleared = PKDrawing()
        guard editHistory.record(
            drawing: cleared,
            backgroundImage: backgroundImage
        ) else {
            return
        }

        liveSaveScheduler.cancelPending()
        let snapshot = CanvasEditHistoryController.Snapshot(
            drawing: cleared,
            backgroundImage: backgroundImage
        )
        activeTool.applyHistorySnapshot(snapshot)
        localDrawing = cleared
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
        let canvasSize = logicalCanvasSize
        let pencil = activeTool.pencilSettings
        saveRetryController.submitSave {
            bridge.save(
                drawing: drawing,
                backgroundImage: backgroundImage,
                logicalCanvasSize: canvasSize,
                pencil: pencil,
                persistBackground: persistBackground
            )
            return bridge.status == "Saving…"
        }
    }

    private func handleBridgeStatus(_ status: String) {
        if status.hasPrefix("Saved —") {
            saveRetryController.acknowledgeSave()
        }
        if status == "Recent graphic is no longer available" {
            documentNavigation.cancelPendingNavigation()
        }
    }

    private func navigateBack() {
        navigate(to: documentNavigation.backPath())
    }

    private func navigateForward() {
        navigate(to: documentNavigation.forwardPath())
    }

    private func navigate(to path: String?) {
        guard let path, path != bridge.selectedPath else { return }
        quickToolPaletteAnchor = nil
        liveSaveScheduler.cancelPending()
        saveCurrentState(persistBackground: false)
        bridge.requestOpen(path: path)
    }

    private func closeCurrentImage() {
        guard bridge.selectedPath != nil else { return }
        quickToolPaletteAnchor = nil
        liveSaveScheduler.cancelPending()
        saveCurrentState(persistBackground: false)
        let deferred = saveRetryController.closeWhenSettled {
            bridge.closeCurrentDocumentKeepingListener()
        }
        if deferred {
            bridge.status = "Saving before closing…"
        }
    }

    private func consumePendingRemoteDocument() {
        guard let token = pendingRemoteToken else { return }
        pendingRemoteToken = nil
        loadRemoteDocument(token: token)
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
        liveSaveScheduler.cancelPending()
        canvasWidth = max(width.rounded(), 64)
        canvasHeight = max(height.rounded(), 64)
        rememberedCanvasWidth = canvasWidth
        rememberedCanvasHeight = canvasHeight
        canvasWidthText = String(Int(canvasWidth))
        canvasHeightText = String(Int(canvasHeight))
        if saveGate.allowsSave(path: bridge.selectedPath) {
            bridge.saveCanvasSize(logicalCanvasSize: logicalCanvasSize)
        }
        editHistory.reset(
            drawing: localDrawing,
            backgroundImage: backgroundImage
        )
        bindToolRuntime()
    }

    private func importPhoto(_ item: PhotosPickerItem?) {
        guard let item else { return }
        Task {
            guard let data = try? await item.loadTransferable(type: Data.self),
                  let image = UIImage(data: data) else {
                return
            }
            await MainActor.run {
                selectedPhotoItem = nil
                guard let merged = rasterComposer.inserting(
                    image: image,
                    into: backgroundImage,
                    canvasSize: logicalCanvasSize
                ),
                editHistory.record(
                    drawing: localDrawing,
                    backgroundImage: merged
                ) else {
                    return
                }
                liveSaveScheduler.cancelPending()
                backgroundImage = merged
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
        guard let selectedPath = bridge.selectedPath else {
            return "ND Graphic"
        }
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
