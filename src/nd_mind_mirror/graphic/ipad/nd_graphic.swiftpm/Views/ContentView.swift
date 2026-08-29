import Foundation
import PencilKit
import PhotosUI
import SwiftUI
import UIKit

/// Main iPad drawing screen. Active drawing state lives in ActiveDrawingToolController.
struct ContentView: View {
    @StateObject private var bridge = GraphicBridgeClient()
    @StateObject private var activeTool = ActiveDrawingToolController()
    @StateObject private var savedTools = SavedDrawingToolStore()
    @StateObject private var recentColors = RecentPencilColors()

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
    @State private var canvasUndoManager: UndoManager?
    @State private var selectedPhotoItem: PhotosPickerItem?
    @State private var editingToolID: UUID?
    @State private var editorColor: Color = .black
    @State private var editorWidth: Double = 1.5
    @State private var editorOpacity: Double = 1
    @State private var editorEraserMode: EraserMode = .whole
    @State private var showCanvasEditor = false
    @State private var canvasWidthText = "1240"
    @State private var canvasHeightText = "1754"
    @State private var saveTask: Task<Void, Never>?
    @State private var loadedPath: String?
    @State private var lastLocalEdit = Date.distantPast
    @State private var initializedTool = false

    var body: some View {
        VStack(spacing: 0) {
            header
            if bridge.selectedPath == nil {
                connectionScreen
            } else {
                drawingScreen
            }
        }
        .popover(isPresented: $showCanvasEditor) { canvasEditor }
        .onAppear {
            if !initializedTool {
                initializedTool = true
                if let first = savedTools.tools.first { activeTool.select(savedTool: first) }
            }
            bindToolRuntime()
        }
        .onChange(of: bridge.documentToken) { _, token in loadRemoteDocument(token: token) }
        .onChange(of: activeTool.state) { _, _ in bindToolRuntime() }
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
            Text("Connect to Mind Mirror").font(.largeTitle.bold())
            Text("iPad listens on TCP 8768; Ubuntu connects automatically.")
                .foregroundStyle(.secondary)
            SecureField("Token (optional)", text: $bridge.token)
                .textFieldStyle(.roundedBorder)
                .frame(maxWidth: 480)
            Button("Start listening for Ubuntu") { bridge.connect() }
                .buttonStyle(.borderedProminent)
            Text(bridge.status).font(.caption).foregroundStyle(.secondary)
            Spacer()
        }
        .padding(24)
    }

    private var drawingScreen: some View {
        VStack(spacing: 0) {
            toolbar
            statusBar
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
                showMeasurementRulers: showMeasurementRulers,
                zoom100RequestToken: zoom100RequestToken,
                onDrawingChanged: { drawing in
                    lastLocalEdit = Date()
                    localDrawing = drawing
                    scheduleSave(drawing: drawing)
                },
                onUndoManagerChanged: { manager in
                    canvasUndoManager = manager
                },
                onZoomChanged: { zoomScale = $0 },
                onImageObjectSelectionChanged: { _ in },
                onImageObjectsCommitted: { _, _, _ in }
            )
            .clipped()
            .onAppear { bindToolRuntime() }
        }
    }

    private var toolbar: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 7) {
                ForEach(savedTools.tools) { saved in
                    SavedDrawingToolControl(
                        savedTool: saved,
                        isActive: activeTool.isSelected(saved),
                        onSelect: { select(saved) },
                        onEdit: { openEditor(saved) }
                    )
                    .frame(width: 42, height: 36)
                    .popover(
                        isPresented: Binding(
                            get: { editingToolID == saved.id },
                            set: { if !$0 && editingToolID == saved.id { editingToolID = nil } }
                        )
                    ) { toolEditor(saved) }
                }

                systemToolButton(.lasso, image: "lasso")
                overlayToggleButton(isOn: $showMeasurementGrid, image: "square.grid.3x3", label: "Grid")
                overlayToggleButton(isOn: $showMeasurementRulers, image: "ruler", label: "Rulers")

                PhotosPicker(selection: $selectedPhotoItem, matching: .images) {
                    Image(systemName: "photo.badge.plus").frame(width: 30, height: 30)
                }
                .buttonStyle(.bordered)
                .onChange(of: selectedPhotoItem) { _, item in importPhoto(item) }

                Button { canvasUndoManager?.undo() } label: { Image(systemName: "arrow.uturn.backward") }
                    .disabled(!(canvasUndoManager?.canUndo ?? false))
                Button { canvasUndoManager?.redo() } label: { Image(systemName: "arrow.uturn.forward") }
                    .disabled(!(canvasUndoManager?.canRedo ?? false))

                Menu {
                    Button("100% zoom") { zoom100RequestToken += 1 }
                    Divider()
                    Button("A4 portrait — 1240 × 1754") { setCanvas(width: 1240, height: 1754) }
                    Button("A4 landscape — 1754 × 1240") { setCanvas(width: 1754, height: 1240) }
                    Button("Square — 1600 × 1600") { setCanvas(width: 1600, height: 1600) }
                    Button("Custom canvas size…") {
                        canvasWidthText = String(Int(canvasWidth))
                        canvasHeightText = String(Int(canvasHeight))
                        showCanvasEditor = true
                    }
                    Divider()
                    Button("Clear drawing", role: .destructive) {
                        localDrawing = PKDrawing()
                        canvasToken += 1
                        scheduleSave(drawing: localDrawing, immediate: true)
                    }
                    Button("Disconnect", role: .destructive) { bridge.disconnect() }
                } label: {
                    Image(systemName: "ellipsis.circle").frame(width: 30, height: 30)
                }
            }
            .controlSize(.small)
            .padding(.horizontal, 8)
            .padding(.vertical, 6)
        }
        .background(.bar)
    }

    private var statusBar: some View {
        HStack(spacing: 12) {
            Text(activeToolName).font(.caption2.bold()).foregroundStyle(Color.accentColor)
            Text("\(Int((zoomScale * 100).rounded()))%").font(.caption2.monospacedDigit())
            Text("\(Int(canvasWidth)) × \(Int(canvasHeight))").font(.caption2.monospacedDigit())
            Spacer()
            if activeTool.kind == .eraser {
                Text("\(activeTool.eraserMode.title) • \(Int(activeTool.width)) px • strokes + loaded image")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 4)
        .background(Color(uiColor: .secondarySystemBackground))
    }

    @ViewBuilder
    private func systemToolButton(_ kind: GraphicTool, image: String) -> some View {
        let selected = activeTool.kind == kind && activeTool.selectedSavedToolID == nil
        Button {
            activeTool.select(kind: kind)
            bindToolRuntime()
        } label: {
            Image(systemName: image)
                .frame(width: 32, height: 32)
                .background(selected ? Color.accentColor.opacity(0.18) : Color.clear)
                .overlay {
                    RoundedRectangle(cornerRadius: 8)
                        .stroke(selected ? Color.accentColor : Color.secondary.opacity(0.25), lineWidth: selected ? 2.5 : 0.7)
                }
                .clipShape(RoundedRectangle(cornerRadius: 8))
        }
        .buttonStyle(.plain)
    }

    private func overlayToggleButton(isOn: Binding<Bool>, image: String, label: String) -> some View {
        Button {
            isOn.wrappedValue.toggle()
        } label: {
            Image(systemName: image)
                .frame(width: 32, height: 32)
                .background(isOn.wrappedValue ? Color.accentColor.opacity(0.18) : Color.clear)
                .overlay {
                    RoundedRectangle(cornerRadius: 8)
                        .stroke(
                            isOn.wrappedValue ? Color.accentColor : Color.secondary.opacity(0.25),
                            lineWidth: isOn.wrappedValue ? 2.0 : 0.7
                        )
                }
                .clipShape(RoundedRectangle(cornerRadius: 8))
        }
        .buttonStyle(.plain)
        .accessibilityLabel(label)
        .accessibilityValue(isOn.wrappedValue ? "On" : "Off")
    }

    private func select(_ saved: SavedDrawingTool) {
        activeTool.select(savedTool: saved)
        if saved.kind.supportsColor {
            recentColors.remember(hex: saved.colorHex, for: saved.kind)
        }
        bindToolRuntime()
    }

    private func openEditor(_ saved: SavedDrawingTool) {
        select(saved)
        editorColor = Color(hex: saved.colorHex)
        editorWidth = saved.width
        editorOpacity = saved.opacity
        editorEraserMode = saved.eraserMode
        editingToolID = saved.id
    }

    @ViewBuilder
    private func toolEditor(_ saved: SavedDrawingTool) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Text(saved.kind == .eraser
                     ? "Eraser settings"
                     : (saved.kind == .highlighter ? "Highlighter settings" : "Pencil settings"))
                    .font(.headline)
                Spacer()
                Button("Done") { editingToolID = nil }
                    .buttonStyle(.bordered)
            }

            if saved.kind == .eraser {
                Picker("Mode", selection: $editorEraserMode) {
                    ForEach(EraserMode.allCases) { mode in
                        Text(mode.title).tag(mode)
                    }
                }
                .pickerStyle(.segmented)

                HStack {
                    Text("Thickness")
                    Slider(value: $editorWidth, in: 2...120, step: 1)
                    Text("\(Int(editorWidth.rounded())) px")
                        .monospacedDigit()
                        .frame(width: 58)
                }

                Text(editorEraserMode == .partial
                     ? "Partial removes only the touched part of a PencilKit stroke."
                     : "Whole removes the entire PencilKit stroke that the eraser touches.")
                    .font(.caption)
                    .foregroundStyle(.secondary)

                Text("On the loaded bitmap image, both modes erase only the pixels under the eraser because a flattened bitmap has no separate stroke identity.")
                    .font(.caption2)
                    .foregroundStyle(.secondary)

                HStack {
                    Button("Add after current") {
                        let id = savedTools.addEraser(
                            mode: editorEraserMode,
                            width: editorWidth,
                            after: saved.id
                        )
                        if let created = savedTools.tools.first(where: { $0.id == id }) {
                            select(created)
                            openEditor(created)
                        }
                    }
                    .buttonStyle(.borderedProminent)

                    Button("Change current") {
                        savedTools.updateEraser(
                            id: saved.id,
                            mode: editorEraserMode,
                            width: editorWidth
                        )
                        if let updated = savedTools.tools.first(where: { $0.id == saved.id }) {
                            select(updated)
                        }
                    }
                    .buttonStyle(.bordered)
                }
            } else {
                ColorPicker("Color", selection: $editorColor, supportsOpacity: false)
                let recent = recentColors.hexColors(for: saved.kind)
                if !recent.isEmpty {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 8) {
                            ForEach(recent, id: \.self) { hex in
                                Button {
                                    editorColor = Color(hex: hex)
                                    recentColors.remember(hex: hex, for: saved.kind)
                                } label: {
                                    Circle()
                                        .fill(Color(hex: hex))
                                        .frame(width: 30, height: 30)
                                        .overlay(Circle().stroke(Color.secondary.opacity(0.3), lineWidth: 1))
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }
                }
                HStack {
                    Text("Thickness")
                    Slider(value: $editorWidth, in: 0.5...60, step: 0.5)
                    Text(editorWidth.formatted(.number.precision(.fractionLength(0...1))))
                        .monospacedDigit().frame(width: 40)
                }
                HStack {
                    Text("Opacity")
                    Slider(value: $editorOpacity, in: 0.05...1, step: 0.05)
                    Text("\(Int((editorOpacity * 100).rounded()))%")
                        .monospacedDigit().frame(width: 44)
                }
                HStack {
                    Button("Add after current") {
                        if let id = savedTools.add(
                            kind: saved.kind,
                            color: editorColor,
                            width: editorWidth,
                            opacity: editorOpacity,
                            after: saved.id
                        ), let created = savedTools.tools.first(where: { $0.id == id }) {
                            select(created)
                            openEditor(created)
                        }
                    }
                    .buttonStyle(.borderedProminent)

                    Button("Change current") {
                        savedTools.update(
                            id: saved.id,
                            kind: saved.kind,
                            color: editorColor,
                            width: editorWidth,
                            opacity: editorOpacity
                        )
                        if let updated = savedTools.tools.first(where: { $0.id == saved.id }) {
                            select(updated)
                        }
                    }
                    .buttonStyle(.bordered)
                }
            }

            Button("Delete current tool", role: .destructive) {
                let wasActive = activeTool.selectedSavedToolID == saved.id
                savedTools.remove(id: saved.id)
                editingToolID = nil
                if wasActive {
                    if let replacement = savedTools.tools.first {
                        select(replacement)
                    } else {
                        activeTool.select(kind: .pencil)
                    }
                }
            }
        }
        .padding(18)
        .frame(minWidth: 400)
    }

    private var canvasEditor: some View {
        NavigationStack {
            Form {
                TextField("Width", text: $canvasWidthText).keyboardType(.asciiCapableNumberPad)
                TextField("Height", text: $canvasHeightText).keyboardType(.asciiCapableNumberPad)
            }
            .navigationTitle("Canvas Size")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { showCanvasEditor = false } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Apply") {
                        setCanvas(width: Double(canvasWidthText) ?? canvasWidth, height: Double(canvasHeightText) ?? canvasHeight)
                        showCanvasEditor = false
                    }
                }
            }
        }
        .frame(minWidth: 420, minHeight: 300)
    }

    private func loadRemoteDocument(token: Int) {
        guard token != localToken else { return }
        localToken = token
        guard let path = bridge.selectedPath else {
            loadedPath = nil
            return
        }
        if path == loadedPath && Date().timeIntervalSince(lastLocalEdit) < 3 { return }

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
        let sourceBackground = bridge.backgroundImageForCurrentDocument()
        backgroundImage = rasterComposer.flatten(
            backgroundImage: sourceBackground,
            legacyImageObjects: legacyObjects,
            canvasSize: logicalCanvasSize
        )
        CanvasImageObjectStore.clear(documentIdentifier: path)

        if let remote = bridge.document?.pencil {
            activeTool.adoptDocumentPencil(width: remote.width, colorHex: remote.color)
        }

        canvasToken += 1
        if newDocument { zoom100RequestToken += 1 }
        bindToolRuntime()

        if !legacyObjects.isEmpty {
            lastLocalEdit = Date()
            saveTask?.cancel()
            bridge.save(
                drawing: localDrawing,
                backgroundImage: backgroundImage,
                logicalCanvasSize: logicalCanvasSize,
                pencil: activeTool.pencilSettings,
                persistBackground: true
            )
        }
    }

    private func bindToolRuntime() {
        activeTool.bindRuntime(
            canvasSize: logicalCanvasSize,
            backgroundImageChanged: { image in
                lastLocalEdit = Date()
                backgroundImage = image
                saveTask?.cancel()
                bridge.save(
                    drawing: localDrawing,
                    backgroundImage: image,
                    logicalCanvasSize: logicalCanvasSize,
                    pencil: activeTool.pencilSettings,
                    persistBackground: true
                )
            },
            undoManagerChanged: { manager in
                canvasUndoManager = manager
            }
        )
    }

    private func scheduleSave(drawing: PKDrawing, immediate: Bool = false) {
        saveTask?.cancel()
        let settings = activeTool.pencilSettings
        saveTask = Task { @MainActor in
            if !immediate { try? await Task.sleep(nanoseconds: 850_000_000) }
            guard !Task.isCancelled else { return }
            bridge.save(
                drawing: drawing,
                backgroundImage: backgroundImage,
                logicalCanvasSize: logicalCanvasSize,
                pencil: settings
            )
        }
    }

    private func setCanvas(width: Double, height: Double) {
        saveTask?.cancel()
        canvasWidth = max(width.rounded(), 64)
        canvasHeight = max(height.rounded(), 64)
        rememberedCanvasWidth = canvasWidth
        rememberedCanvasHeight = canvasHeight
        canvasWidthText = String(Int(canvasWidth))
        canvasHeightText = String(Int(canvasHeight))
        bridge.saveCanvasSize(logicalCanvasSize: logicalCanvasSize)
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
                ) else { return }

                backgroundImage = merged
                lastLocalEdit = Date()
                saveTask?.cancel()
                bridge.save(
                    drawing: localDrawing,
                    backgroundImage: merged,
                    logicalCanvasSize: logicalCanvasSize,
                    pencil: activeTool.pencilSettings,
                    persistBackground: true
                )
            }
        }
    }

    private var logicalCanvasSize: CGSize {
        CGSize(width: CGFloat(max(canvasWidth, 64)), height: CGFloat(max(canvasHeight, 64)))
    }

    private var graphicContextTitle: String {
        guard let selectedPath = bridge.selectedPath else { return "ND Graphic" }
        let sidecarURL = URL(fileURLWithPath: selectedPath)
        let folder = sidecarURL.deletingLastPathComponent().lastPathComponent
        let imageName = bridge.document?.imageName?.trimmingCharacters(in: .whitespacesAndNewlines)
        let resolvedImageName = (imageName?.isEmpty == false)
            ? imageName!
            : sidecarURL.deletingPathExtension().lastPathComponent + ".png"
        return folder.isEmpty ? resolvedImageName : "\(folder) / \(resolvedImageName)"
    }

    private var activeToolName: String {
        switch activeTool.kind {
        case .pencil: return "Pencil \(activeTool.width.formatted(.number.precision(.fractionLength(0...1)))) px"
        case .highlighter: return "Marker \(activeTool.width.formatted(.number.precision(.fractionLength(0...1)))) px"
        case .eraser: return "\(activeTool.eraserMode.title) Eraser \(Int(activeTool.width.rounded())) px"
        case .lasso: return "Lasso"
        }
    }
}
