// Builds the native iPad drawing workflow, including floating recent colors, explicit 100% zoom, persistent stroke settings, and lasso selection.
// ND_MIND_MIRROR_IPAD_LAYOUT_20260823

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
    @State private var recentGraphics: [RecentGraphicItem] = RecentGraphicStore.load()
    @AppStorage("graphic.last.canvas.width") private var rememberedCanvasWidth: Double = 1240
    @AppStorage("graphic.last.canvas.height") private var rememberedCanvasHeight: Double = 1754
    // ND_DYNAMIC_TOOLBAR_STATE_V1
    @StateObject private var savedTools = SavedDrawingToolStore()
    @State private var editingSavedToolID: UUID?
    @StateObject private var imageObjectManager = CanvasImageObjectManager()
    @AppStorage("graphic.stroke.lastOpacity") private var toolOpacity: Double = 1.0
    @State private var localDrawing = PKDrawing()
    @State private var backgroundImage: UIImage?
    @State private var selectedPhotoItem: PhotosPickerItem?
    @State private var localToken = -1
    @State private var canvasToken = 0
    @State private var canvasWidth: Double = 1240
    @State private var canvasHeight: Double = 1754
    @State private var canvasWidthText = "1240"
    @State private var canvasHeightText = "1754"
    @State private var zoomScale: CGFloat = 1.0
    @State private var zoom100RequestToken = 0
    @State private var showCanvasSizeEditor = false
    @State private var showRecentColors = false
    @State private var saveTask: Task<Void, Never>?
    @State private var canvasUndoManager: UndoManager?
    @State private var showDiagnostics = true
    @State private var showMeasurementGrid = true
    @State private var showMeasurementRulers = true

    // ND_CONTENT_BUNDLE_VERSION_V1
    private var displayVersion: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "unknown"
    }

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
            // ND_IMAGE_OBJECT_DOCUMENT_LOAD_V1
            if let path = bridge.selectedPath {
                if bridge.currentOperation == "insert" {
                    imageObjectManager.beginNewDocument(documentIdentifier: path)
                } else {
                    imageObjectManager.load(
                        documentIdentifier: path,
                        remoteObjects: bridge.document?.imageObjects
                    )
                }
            } else {
                imageObjectManager.load(documentIdentifier: "")
            }

            if bridge.currentOperation == "insert" {
                canvasWidth = max(rememberedCanvasWidth.rounded(), 64)
                canvasHeight = max(rememberedCanvasHeight.rounded(), 64)
            } else {
                if let width = bridge.document?.canvasWidth, width > 0 {
                    canvasWidth = Double(width)
                }
                if let height = bridge.document?.canvasHeight, height > 0 {
                    canvasHeight = Double(height)
                }
            }
            canvasWidthText = String(Int(canvasWidth))
            canvasHeightText = String(Int(canvasHeight))
            rememberedCanvasWidth = canvasWidth
            rememberedCanvasHeight = canvasHeight

            canvasToken += 1
            if let remotePencil = bridge.document?.pencil {
                if let width = remotePencil.width { pencil.width = width }
                if let color = remotePencil.color {
                    pencil.color = Color(hex: color)
                    recentColors.remember(hex: color, for: tool)
                }
            }
            rememberCurrentGraphic()
            zoom100RequestToken &+= 1

        }
        .onChange(of: tool) { _, _ in
            showRecentColors = false
        }
        // ND_IMAGE_OBJECT_AUTOSAVE_V1
        .onChange(of: imageObjectManager.editRevision) { _, _ in
            scheduleAutosave(drawing: localDrawing, immediate: true)
        }
    }

    /// Shows the compact application/version and bridge connection banner.
    private var startupBanner: some View {
        HStack(spacing: 8) {
            Image(systemName: "pencil.and.scribble")
            Text("ND Graphic v\(displayVersion)")
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

    /// Shows the active toolbar, canvas status, and PencilKit drawing surface without palette-driven layout shifts.
    private var drawingScreen: some View {
        VStack(spacing: 0) {
            toolbar
            canvasStatusBar
            PencilCanvasView(
                drawing: localDrawing,
                backgroundImage: backgroundImage,
                documentToken: canvasToken,
                documentIdentifier: bridge.selectedPath ?? "",
                tool: tool,
                color: pencil.color,
                width: pencil.width,
                opacity: toolOpacity,
                imageObjects: imageObjectManager.objects,
                selectedImageObjectID: imageObjectManager.selectedID,
                logicalCanvasSize: logicalCanvasSize,
                showMeasurementGrid: showMeasurementGrid,
                showMeasurementRulers: showMeasurementRulers,
                zoom100RequestToken: zoom100RequestToken,
                onDrawingChanged: { drawing in
                    localDrawing = drawing
                    scheduleAutosave(drawing: drawing)
                },
                onUndoManagerChanged: { manager in
                    canvasUndoManager = manager
                    imageObjectManager.undoManager = manager
                },
                onZoomChanged: { scale in zoomScale = scale },
                onImageObjectSelectionChanged: { id in
                    imageObjectManager.setSelected(id)
                },
                onImageObjectsCommitted: { objects, selectedID, actionName in
                    imageObjectManager.commitFromCanvas(
                        objects,
                        selectedID: selectedID,
                        actionName: actionName
                    )
                }
            )
            .clipped()
        }
    }

    /// Builds the horizontal drawing toolbar with compact stroke controls and a floating recent-color popover.
    private var toolbar: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 6) {
                Text(bridge.currentOperation == "insert" ? "IN" : "UP")
                    .font(.caption2.bold())
                    .padding(.horizontal, 6)
                    .padding(.vertical, 4)
                    .background(Color.accentColor.opacity(0.12), in: Capsule())

                Button {
                    showMeasurementGrid.toggle()
                } label: {
                    Label(showMeasurementGrid ? "Grid" : "Grid off", systemImage: "grid")
                }
                .buttonStyle(.bordered)
                .controlSize(.small)
                .help("Show or hide the 0.5 cm measurement grid")

                Button {
                    showMeasurementRulers.toggle()
                } label: {
                    Label(showMeasurementRulers ? "Ruler" : "Ruler off", systemImage: "ruler")
                }
                .buttonStyle(.bordered)
                .controlSize(.small)
                .help("Show or hide the top and left centimeter rulers")

                // ND_TOOL_POPUP_MIGRATION4
                ForEach(savedTools.tools) { saved in
                    Button {
                        applySavedTool(saved)
                        editingSavedToolID = saved.id
                    } label: {
                        Image(systemName: saved.kind == .highlighter ? "highlighter" : "pencil")
                            .symbolRenderingMode(.monochrome)
                            .font(.system(
                                size: CGFloat(min(max(16.0 + saved.width * 0.22, 17.0), 29.0)),
                                weight: saved.width >= 40 ? .black
                                    : saved.width >= 24 ? .bold
                                    : saved.width >= 12 ? .semibold
                                    : saved.width >= 5 ? .medium
                                    : .regular
                            ))
                            .foregroundStyle(Color(hex: saved.colorHex).opacity(saved.opacity))
                            .frame(width: 34, height: 28)
                            .background(
                                isSavedToolActive(saved) ? Color.accentColor.opacity(0.18) : Color.clear,
                                in: RoundedRectangle(cornerRadius: 7)
                            )
                    }
                    .buttonStyle(.plain)
                    .popover(
                        isPresented: Binding(
                            get: { editingSavedToolID == saved.id },
                            set: { presented in
                                if !presented && editingSavedToolID == saved.id {
                                    editingSavedToolID = nil
                                }
                            }
                        ),
                        arrowEdge: .top
                    ) {
                        savedToolEditor(saved)
                    }
                }

                toolButton(.eraser, systemImage: "eraser")
                toolButton(.lasso, systemImage: "lasso")

                PhotosPicker(selection: $selectedPhotoItem, matching: .images) {
                    Image(systemName: "photo.badge.plus")
                        .frame(width: 28, height: 28)
                }
                .buttonStyle(.bordered)
                .onChange(of: selectedPhotoItem) { _, item in importPhoto(item) }

                // ND_IMAGE_DELETE_BUTTON_V1
                Button {
                    imageObjectManager.deleteSelected()
                } label: {
                    Image(systemName: "trash")
                }
                .disabled(imageObjectManager.selectedID == nil)
                .help("Delete selected image object")

                Button { canvasUndoManager?.undo() } label: { Image(systemName: "arrow.uturn.backward") }
                    .disabled(!(canvasUndoManager?.canUndo ?? false))
                Button { canvasUndoManager?.redo() } label: { Image(systemName: "arrow.uturn.forward") }
                    .disabled(!(canvasUndoManager?.canRedo ?? false))

                Menu {
                    Text("Current • \(Int(canvasWidth)) × \(Int(canvasHeight)) px")
                        .foregroundStyle(.blue)
                    Divider()
                    Button("A4 portrait — 21 × 29.7 cm — 1240 × 1754") { setCanvasSize(width: 1240, height: 1754) }
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

    /// Shows source/image identity, zoom controls, and logical canvas size above the canvas.
    private var canvasStatusBar: some View {
        HStack(spacing: 12) {
            Menu {
                if recentGraphics.isEmpty {
                    Text("No recent graphics")
                } else {
                    ForEach(recentGraphics) { item in
                        Button(item.label) {
                            bridge.requestOpen(path: item.path)
                        }
                    }
                }
            } label: {
                Text(activeGraphicLabel)
                    .font(.caption2.weight(.semibold))
                    .lineLimit(1)
                    .truncationMode(.middle)
            }
            .help("Open one of the ten most recently edited graphics")

            Menu {
                Button("100%") {
                    zoom100RequestToken &+= 1
                }
            } label: {
                Label("\(Int((zoomScale * 100).rounded()))%", systemImage: "magnifyingglass")
            }
            .buttonStyle(.bordered)
            .controlSize(.mini)
            .help("Zoom options")
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

    /// Edits one Pencil/Highlighter configuration in a dedicated popup.
    @ViewBuilder
    private func savedToolEditor(_ saved: SavedDrawingTool) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Image(systemName: saved.kind == .highlighter ? "highlighter" : "pencil")
                Text(saved.kind == .highlighter ? "Highlighter" : "Pencil")
                    .font(.headline)
                Spacer()
            }

            ColorPicker("Color", selection: toolColorBinding, supportsOpacity: false)

            VStack(alignment: .leading, spacing: 4) {
                Text("Thickness")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Slider(value: $pencil.width, in: 0.5...60, step: 0.5)
            }

            VStack(alignment: .leading, spacing: 4) {
                Text("Transparency")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Slider(
                    value: Binding(
                        get: { 1.0 - toolOpacity },
                        set: { toolOpacity = 1.0 - $0 }
                    ),
                    in: 0.0...0.95,
                    step: 0.05
                )
            }

            HStack {
                Button {
                    if let newID = savedTools.add(
                        kind: saved.kind,
                        color: pencil.color,
                        width: pencil.width,
                        opacity: toolOpacity,
                        after: saved.id
                    ) {
                        editingSavedToolID = newID
                    }
                } label: {
                    Label("Add after current", systemImage: "plus")
                }
                .buttonStyle(.borderedProminent)

                Button("Change current") {
                    savedTools.update(
                        id: saved.id,
                        kind: saved.kind,
                        color: pencil.color,
                        width: pencil.width,
                        opacity: toolOpacity
                    )
                }
                .buttonStyle(.bordered)
            }

            Divider()
            Text("Saved \(saved.kind == .highlighter ? "highlighters" : "pencils")")
                .font(.caption)
                .foregroundStyle(.secondary)
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(savedTools.tools.filter { $0.kind == saved.kind }) { other in
                        Button {
                            applySavedTool(other)
                            editingSavedToolID = other.id
                        } label: {
                            Image(systemName: other.kind == .highlighter ? "highlighter" : "pencil")
                                .foregroundStyle(Color(hex: other.colorHex).opacity(other.opacity))
                                .frame(width: 32, height: 28)
                                .background(
                                    other.id == saved.id ? Color.accentColor.opacity(0.16) : Color.clear,
                                    in: RoundedRectangle(cornerRadius: 7)
                                )
                        }
                        .buttonStyle(.plain)
                    }
                }
            }

            Button("Delete current tool", role: .destructive) {
                savedTools.remove(id: saved.id)
                editingSavedToolID = nil
            }
        }
        .padding(18)
        .frame(minWidth: 360)
        .onAppear {
            applySavedTool(saved)
        }
    }

    /// Applies one persistent toolbar drawing tool.
    private func applySavedTool(_ saved: SavedDrawingTool) {
        tool = saved.kind
        pencil.color = Color(hex: saved.colorHex)
        pencil.width = saved.width
        toolOpacity = saved.opacity
        recentColors.remember(hex: saved.colorHex, for: saved.kind)
    }

    private func isSavedToolActive(_ saved: SavedDrawingTool) -> Bool {
        guard tool == saved.kind else { return false }
        let sameColor = pencil.color.hexRGB().uppercased() == saved.colorHex.uppercased()
        return sameColor
            && abs(pencil.width - saved.width) < 0.01
            && abs(toolOpacity - saved.opacity) < 0.01
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

    /// Displays ten recent colors in a compact floating five-column palette and closes after selection.
    private var recentColorGrid: some View {
        let colors = recentColors.matrixHexColors(for: tool)
        let columns = Array(repeating: GridItem(.fixed(32), spacing: 6), count: 5)
        return VStack(alignment: .leading, spacing: 8) {
            Text("Recent colors")
                .font(.caption.bold())
            LazyVGrid(columns: columns, alignment: .leading, spacing: 6) {
                ForEach(colors, id: \.self) { hex in
                    let swatch = Color(hex: hex)
                    Button {
                        pencil.color = swatch
                        recentColors.remember(hex: hex, for: tool)
                        showRecentColors = false
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
        }
        .padding(12)
        .frame(width: 214)
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
                    TextField("Width", text: $canvasWidthText).keyboardType(.asciiCapableNumberPad)
                    TextField("Height", text: $canvasHeightText).keyboardType(.asciiCapableNumberPad)
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
    private var activeGraphicLabel: String {
        if let sourceName = bridge.document?.sourceName,
           let imageName = bridge.document?.imageName {
            return "\(sourceName) > \(imageName)"
        }
        if let imageName = bridge.document?.imageName { return imageName }
        if let path = bridge.selectedPath { return URL(fileURLWithPath: path).lastPathComponent }
        return "Graphic"
    }

    private var minimumCanvasSize: CGSize {
        let bounds = localDrawing.bounds
        return CGSize(
            width: max(64, ceil(max(bounds.maxX, 0) + 8)),
            height: max(64, ceil(max(bounds.maxY, 0) + 8))
        )
    }

    private func rememberCurrentGraphic() {
        guard let path = bridge.selectedPath else { return }
        recentGraphics = RecentGraphicStore.remember(path: path, label: activeGraphicLabel)
    }


    private var logicalCanvasSize: CGSize {
        CGSize(width: CGFloat(max(canvasWidth, 64)), height: CGFloat(max(canvasHeight, 64)))
    }

    /// Resizes the logical canvas without clipping existing PencilKit strokes.
    private func setCanvasSize(width: Double, height: Double) {
        let requestedWidth = max(width.rounded(), 64)
        let requestedHeight = max(height.rounded(), 64)
        let minimum = minimumCanvasSize
        guard requestedWidth >= minimum.width && requestedHeight >= minimum.height else {
            bridge.status = "Canvas cannot be smaller than the graphic (minimum \(Int(ceil(minimum.width))) × \(Int(ceil(minimum.height))) px)"
            return
        }
        canvasWidth = requestedWidth
        canvasHeight = requestedHeight
        canvasWidthText = String(Int(canvasWidth))
        canvasHeightText = String(Int(canvasHeight))
        rememberedCanvasWidth = canvasWidth
        rememberedCanvasHeight = canvasHeight
        bridge.save(
            drawing: localDrawing,
            backgroundImage: backgroundImage,
            logicalCanvasSize: logicalCanvasSize,
            pencil: pencil
        )
        zoom100RequestToken &+= 1
    }

    /// Inserts a selected Photos image as an editable object instead of replacing the document background.
    private func importPhoto(_ item: PhotosPickerItem?) {
        guard let item else { return }
        Task {
            guard let data = try? await item.loadTransferable(type: Data.self),
                  let image = UIImage(data: data) else {
                await MainActor.run { bridge.status = "Could not load the selected photo" }
                return
            }
            await MainActor.run {
                selectedPhotoItem = nil
                if imageObjectManager.insert(image: image, canvasSize: logicalCanvasSize) != nil {
                    tool = .lasso
                    bridge.status = "Image inserted — use Lasso/finger to move or resize"
                } else {
                    bridge.status = "Could not insert the selected photo"
                }
            }
        }
    }

}
