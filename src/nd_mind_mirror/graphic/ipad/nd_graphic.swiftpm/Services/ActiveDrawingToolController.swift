import PencilKit
import SwiftUI
import UIKit

/// Owns the active PencilKit tool, atomic canvas history, raster editing, and finger navigation safety.
@MainActor
final class ActiveDrawingToolController: NSObject, ObservableObject, UIGestureRecognizerDelegate {
    struct State: Equatable {
        var kind: GraphicTool
        var colorHex: String
        var width: Double
        var opacity: Double
        var eraserMode: EraserMode
        var selectedSavedToolID: UUID?
    }

    @Published private(set) var state: State
    @Published private(set) var isRasterEditing = false
    @Published private(set) var isPencilGestureActive = false

    private weak var canvas: PKCanvasView?
    private weak var backgroundView: UIImageView?
    private weak var rasterSurfaceView: UIView?
    private weak var observedDrawingGesture: UIGestureRecognizer?
    private weak var parentScrollView: UIScrollView?
    private weak var historyUndoGesture: UITapGestureRecognizer?
    private weak var historyController: CanvasEditHistoryController?
    private let stateStore: ActiveDrawingToolStateStore
    private let lassoSelectionFeedbackController = LassoSelectionFeedbackController()
    private let rasterLassoInteractionController = RasterLassoInteractionController()
    private var rasterSession: RasterEraseSession?
    private var pendingRasterImage: UIImage?
    private var pendingRasterChanged = false
    private var rasterPreviewLayer: CAShapeLayer?
    private var canvasSize = CGSize(width: 1240, height: 1754)
    private var canvasStateCommitted: ((PKDrawing, UIImage?, Bool) -> Void)?
    private var undoRequested: (() -> Void)?
    private var pendingProgrammaticDrawingData: Data?

    override init() {
        let stateStore = ActiveDrawingToolStateStore()
        let persisted = stateStore.load()
        self.stateStore = stateStore
        self.state = State(
            kind: persisted.kind,
            colorHex: persisted.colorHex,
            width: persisted.width,
            opacity: persisted.opacity,
            eraserMode: persisted.eraserMode,
            selectedSavedToolID: persisted.selectedSavedToolID
        )
        super.init()
        state = canonicalized(state)
        lassoSelectionFeedbackController.onLassoCompleted = { [weak self] points in
            guard let self, self.state.kind == .lasso else { return }
            self.rasterLassoInteractionController.selectRasterRegion(with: points)
        }
    }

    var kind: GraphicTool { state.kind }
    var color: Color { Color(hex: state.colorHex) }
    var width: Double { state.width }
    var opacity: Double { state.opacity }
    var eraserMode: EraserMode { state.eraserMode }
    var selectedSavedToolID: UUID? { state.selectedSavedToolID }
    var pencilSettings: PencilSettings { PencilSettings(width: state.width, color: color) }
    var isCanvasGestureInFlight: Bool {
        if isPencilGestureActive { return true }
        guard let gesture = observedDrawingGesture else { return false }
        return gesture.state == .began || gesture.state == .changed
    }

    /// Attaches tool handling plus non-mutating lasso feedback and raster-region interaction.
    func attach(canvas: PKCanvasView, backgroundView: UIImageView) {
        if self.canvas === canvas {
            self.backgroundView = backgroundView
            rasterSurfaceView = canvas.superview ?? canvas
            lassoSelectionFeedbackController.attach(to: canvas)
            lassoSelectionFeedbackController.setEnabled(state.kind == .lasso)
            rasterLassoInteractionController.attach(
                canvas: canvas,
                backgroundView: backgroundView
            )
            rasterLassoInteractionController.setEnabled(state.kind == .lasso)
            suppressCanvasMenus()
            return
        }

        observedDrawingGesture?.removeTarget(
            self,
            action: #selector(handleDrawingGesture(_:))
        )
        lassoSelectionFeedbackController.detach()
        if let historyUndoGesture {
            historyUndoGesture.view?.removeGestureRecognizer(historyUndoGesture)
        }
        historyUndoGesture = nil

        self.canvas = canvas
        self.backgroundView = backgroundView
        rasterSurfaceView = canvas.superview ?? canvas

        let drawingGesture = canvas.drawingGestureRecognizer
        drawingGesture.allowedTouchTypes = [
            NSNumber(value: UITouch.TouchType.pencil.rawValue)
        ]
        drawingGesture.addTarget(
            self,
            action: #selector(handleDrawingGesture(_:))
        )
        observedDrawingGesture = drawingGesture
        lassoSelectionFeedbackController.attach(to: canvas)
        rasterLassoInteractionController.attach(
            canvas: canvas,
            backgroundView: backgroundView
        )

        configureFingerNavigation(for: canvas)
        clearNativeUndoHistory()
        suppressCanvasMenus()
        DispatchQueue.main.async { [weak self] in
            self?.suppressCanvasMenus()
            self?.clearNativeUndoHistory()
        }
        applyImmediately()
    }

    func bindRuntime(
        canvasSize: CGSize,
        historyController: CanvasEditHistoryController,
        canvasStateCommitted: @escaping (PKDrawing, UIImage?, Bool) -> Void,
        undoRequested: @escaping () -> Void
    ) {
        self.canvasSize = canvasSize
        self.historyController = historyController
        self.canvasStateCommitted = canvasStateCommitted
        self.undoRequested = undoRequested
        rasterLassoInteractionController.bindRuntime(
            canvasSize: canvasSize,
            historyController: historyController,
            canvasStateCommitted: canvasStateCommitted
        )
        applyImmediately()
    }

    /// Clears transient selection and native PencilKit history before a remote document replaces the canvas.
    func prepareForRemoteDocumentLoad() {
        rasterLassoInteractionController.clearSelection()
        pendingProgrammaticDrawingData = nil
        clearNativeUndoHistory()
    }

    /// Reconnect a persisted preset UUID to the current saved-tool collection.
    func reconcileSavedToolSelection(_ tools: [SavedDrawingTool]) {
        guard let selectedID = state.selectedSavedToolID else {
            persistState()
            return
        }
        if let savedTool = tools.first(where: { $0.id == selectedID }) {
            select(savedTool: savedTool)
            return
        }
        var next = state
        next.selectedSavedToolID = nil
        setState(next)
    }

    func select(savedTool: SavedDrawingTool) {
        let selectedWidth = savedTool.kind == .eraser
            ? canonicalEraserWidth(savedTool.width)
            : canonicalInkWidth(savedTool.width)
        setState(State(
            kind: savedTool.kind,
            colorHex: canonicalColor(savedTool.colorHex),
            width: selectedWidth,
            opacity: canonicalOpacity(savedTool.opacity),
            eraserMode: savedTool.eraserMode,
            selectedSavedToolID: savedTool.id
        ))
    }

    func select(kind: GraphicTool) {
        var next = state
        next.kind = kind
        next.selectedSavedToolID = nil
        setState(next)
    }

    func updateAppearance(
        color: Color? = nil,
        width: Double? = nil,
        opacity: Double? = nil
    ) {
        var next = state
        if let color {
            next.colorHex = canonicalColor(color.hexRGB())
        }
        if let width {
            next.width = next.kind == .eraser
                ? canonicalEraserWidth(width)
                : canonicalInkWidth(width)
        }
        if let opacity {
            next.opacity = canonicalOpacity(opacity)
        }
        next.selectedSavedToolID = nil
        setState(next)
    }

    func adoptDocumentPencil(width: Double?, colorHex: String?) {
        guard state.selectedSavedToolID == nil,
              state.kind != .eraser else {
            return
        }
        var next = state
        if let width {
            next.width = canonicalInkWidth(width)
        }
        if let colorHex, !colorHex.isEmpty {
            next.colorHex = canonicalColor(colorHex)
        }
        setState(next)
    }

    func isSelected(_ savedTool: SavedDrawingTool) -> Bool {
        state.selectedSavedToolID == savedTool.id
    }

    private func setState(_ next: State) {
        state = canonicalized(next)
        persistState()
        applyImmediately()
    }

    private func canonicalized(_ value: State) -> State {
        State(
            kind: value.kind,
            colorHex: canonicalColor(value.colorHex),
            width: value.kind == .eraser
                ? canonicalEraserWidth(value.width)
                : canonicalInkWidth(value.width),
            opacity: canonicalOpacity(value.opacity),
            eraserMode: value.eraserMode,
            selectedSavedToolID: value.selectedSavedToolID
        )
    }

    private func persistState() {
        stateStore.save(
            kind: state.kind,
            colorHex: state.colorHex,
            width: state.width,
            opacity: state.opacity,
            eraserMode: state.eraserMode,
            selectedSavedToolID: state.selectedSavedToolID
        )
    }

    private func configureFingerNavigation(for canvas: PKCanvasView) {
        var parent = canvas.superview
        while let view = parent {
            if let scroll = view as? UIScrollView,
               scroll !== canvas {
                parentScrollView = scroll
                scroll.isMultipleTouchEnabled = true
                scroll.panGestureRecognizer.minimumNumberOfTouches = 1
                scroll.panGestureRecognizer.maximumNumberOfTouches = 2
                scroll.panGestureRecognizer.allowedTouchTypes = [
                    NSNumber(value: UITouch.TouchType.direct.rawValue)
                ]
                CanvasInteractionSanitizer.disableLegacyTwoFingerSingleTap(in: scroll)
                installHistoryUndoGesture(on: scroll)
                return
            }
            parent = view.superview
        }
    }

    private func setFingerNavigationEnabled(_ enabled: Bool) {
        parentScrollView?.panGestureRecognizer.isEnabled = enabled
        parentScrollView?.pinchGestureRecognizer?.isEnabled = enabled
    }

    /// Uses one two-finger tap for the app-owned atomic canvas Undo history.
    private func installHistoryUndoGesture(on scroll: UIScrollView) {
        if let historyUndoGesture,
           historyUndoGesture.view === scroll {
            return
        }

        let gesture = UITapGestureRecognizer(
            target: self,
            action: #selector(handleHistoryUndo(_:))
        )
        gesture.numberOfTouchesRequired = 2
        gesture.numberOfTapsRequired = 1
        gesture.allowedTouchTypes = [
            NSNumber(value: UITouch.TouchType.direct.rawValue)
        ]
        gesture.cancelsTouchesInView = false
        gesture.delaysTouchesBegan = false
        gesture.delaysTouchesEnded = false
        gesture.delegate = self
        scroll.addGestureRecognizer(gesture)
        historyUndoGesture = gesture
    }

    @objc private func handleHistoryUndo(_ gesture: UITapGestureRecognizer) {
        guard gesture.state == .ended,
              !isCanvasGestureInFlight else {
            return
        }
        rasterLassoInteractionController.clearSelection()
        undoRequested?()
    }

    /// Applies an Undo/Redo snapshot to the live surfaces before the next Pencil event can start.
    func applyHistorySnapshot(_ snapshot: CanvasEditHistoryController.Snapshot) {
        guard let canvas else { return }
        rasterLassoInteractionController.clearSelection()
        pendingProgrammaticDrawingData = snapshot.drawing.dataRepresentation()
        clearNativeUndoHistory()
        canvas.drawing = snapshot.drawing
        backgroundView?.image = snapshot.backgroundImage
        clearNativeUndoHistory()

        // PencilKit can register delayed native actions after a programmatic drawing assignment.
        // Clear once more on the next run-loop turn so stale strokes cannot resurrect later.
        DispatchQueue.main.async { [weak self] in
            self?.clearNativeUndoHistory()
        }
        suppressCanvasMenus()
    }

    /// Consumes the delegate callback produced by applyHistorySnapshot so it is not recorded as a new edit.
    func consumeProgrammaticDrawingChange(_ drawing: PKDrawing) -> Bool {
        guard let expected = pendingProgrammaticDrawingData,
              expected == drawing.dataRepresentation() else {
            return false
        }
        pendingProgrammaticDrawingData = nil
        return true
    }

    func gestureRecognizer(
        _ gestureRecognizer: UIGestureRecognizer,
        shouldRecognizeSimultaneouslyWith otherGestureRecognizer: UIGestureRecognizer
    ) -> Bool {
        gestureRecognizer === historyUndoGesture
            || otherGestureRecognizer === historyUndoGesture
    }

    private func suppressCanvasMenus() {
        guard let canvas else { return }
        CanvasInteractionSanitizer.suppressMenus(in: canvas)
    }

    /// The app owns lasso selection itself; native PKLassoTool must stay disabled.
    private func configureNativeDrawingGesture(
        for kind: GraphicTool,
        on canvas: PKCanvasView
    ) {
        let shouldEnableNativeDrawing = kind != .lasso
        if canvas.drawingGestureRecognizer.isEnabled != shouldEnableNativeDrawing {
            canvas.drawingGestureRecognizer.isEnabled = shouldEnableNativeDrawing
        }
    }

    private func applyImmediately() {
        guard let canvas else { return }
        suppressCanvasMenus()
        configureNativeDrawingGesture(for: state.kind, on: canvas)
        let lassoEnabled = state.kind == .lasso
        lassoSelectionFeedbackController.setEnabled(lassoEnabled)
        rasterLassoInteractionController.setEnabled(lassoEnabled)

        switch state.kind {
        case .pencil:
            canvas.tool = PKInkingTool(
                .pencil,
                color: UIColor(color).withAlphaComponent(CGFloat(state.opacity)),
                width: CGFloat(state.width)
            )

        case .highlighter:
            canvas.tool = PKInkingTool(
                .marker,
                color: UIColor(color).withAlphaComponent(CGFloat(state.opacity)),
                width: CGFloat(state.width)
            )

        case .eraser:
            let type: PKEraserTool.EraserType = state.eraserMode == .partial
                ? .bitmap
                : .vector
            canvas.tool = PKEraserTool(type, width: CGFloat(state.width))

        case .lasso:
            break
        }
    }

    @objc private func handleDrawingGesture(_ gesture: UIGestureRecognizer) {
        guard let canvas else { return }
        switch gesture.state {
        case .began:
            beginCanvasGesture(gesture, canvas: canvas)

        case .changed:
            if state.kind == .eraser {
                applyRasterPoint(from: gesture)
            }

        case .ended:
            if state.kind == .eraser {
                applyRasterPoint(from: gesture)
                prepareRasterCompletion()
            }
            DispatchQueue.main.async { [weak self] in
                self?.completeCanvasGesture()
            }

        case .cancelled, .failed:
            cancelCanvasGesture()

        default:
            break
        }
    }

    private func beginCanvasGesture(
        _ gesture: UIGestureRecognizer,
        canvas: PKCanvasView
    ) {
        guard !isPencilGestureActive else { return }
        rasterLassoInteractionController.clearSelection()
        clearNativeUndoHistory()
        isPencilGestureActive = true
        setFingerNavigationEnabled(false)
        historyController?.beginGesture()
        pendingRasterImage = nil
        pendingRasterChanged = false

        guard state.kind == .eraser,
              let image = backgroundView?.image,
              let session = RasterEraseSession(
                image: image,
                canvasSize: canvasSize
              ) else {
            return
        }
        rasterSession = session
        isRasterEditing = true
        applyRasterPoint(from: gesture)
    }

    private func applyRasterPoint(from gesture: UIGestureRecognizer) {
        guard state.kind == .eraser,
              let session = rasterSession,
              let surface = rasterSurfaceView,
              let backgroundView else {
            return
        }
        session.erase(
            points: [gesture.location(in: surface)],
            brushDiameter: max(2, CGFloat(state.width))
        )
        guard session.didChange else { return }

        if rasterPreviewLayer == nil {
            let layer = session.makePreviewLayer()
            backgroundView.layer.addSublayer(layer)
            rasterPreviewLayer = layer
        } else if let layer = rasterPreviewLayer {
            session.updatePreviewLayer(layer)
        }
        pendingRasterChanged = true
    }

    private func prepareRasterCompletion() {
        guard let session = rasterSession else { return }
        if session.didChange,
           let finalImage = session.image() {
            backgroundView?.image = finalImage
            pendingRasterImage = finalImage
            pendingRasterChanged = true
        }
        rasterPreviewLayer?.removeFromSuperlayer()
        rasterPreviewLayer = nil
        rasterSession = nil
    }

    private func completeCanvasGesture() {
        guard isPencilGestureActive,
              let canvas else {
            return
        }
        let finalImage = pendingRasterChanged
            ? pendingRasterImage
            : backgroundView?.image
        let finalDrawing = canvas.drawing
        let changed = historyController?.commitGesture(
            drawing: finalDrawing,
            backgroundImage: finalImage
        ) ?? true

        if changed {
            canvasStateCommitted?(
                finalDrawing,
                finalImage,
                pendingRasterChanged
            )
        }
        clearNativeUndoHistory()
        finishGestureState()
    }

    private func cancelCanvasGesture() {
        guard isPencilGestureActive else { return }
        if let snapshot = historyController?.cancelGesture(),
           let canvas {
            pendingProgrammaticDrawingData = snapshot.drawing.dataRepresentation()
            clearNativeUndoHistory()
            canvas.drawing = snapshot.drawing
            backgroundView?.image = snapshot.backgroundImage
            clearNativeUndoHistory()
        }
        finishGestureState()
    }

    private func finishGestureState() {
        rasterPreviewLayer?.removeFromSuperlayer()
        rasterPreviewLayer = nil
        rasterSession = nil
        pendingRasterImage = nil
        pendingRasterChanged = false
        isRasterEditing = false
        isPencilGestureActive = false
        clearNativeUndoHistory()
        setFingerNavigationEnabled(true)
        suppressCanvasMenus()
    }

    private func clearNativeUndoHistory() {
        canvas?.undoManager?.removeAllActions()
    }

    private func canonicalColor(_ raw: String) -> String {
        var value = raw
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .uppercased()
        if value.hasPrefix("#") {
            value.removeFirst()
        }
        if value.count == 8 {
            value = String(value.prefix(6))
        }
        guard value.count == 6,
              value.allSatisfy(\.isHexDigit) else {
            return "#000000"
        }
        return "#\(value)"
    }

    private func canonicalInkWidth(_ value: Double) -> Double {
        min(max(value.isFinite ? value : 1.5, 0.5), 60)
    }

    private func canonicalEraserWidth(_ value: Double) -> Double {
        min(max(value.isFinite ? value : 18, 2), 120)
    }

    private func canonicalOpacity(_ value: Double) -> Double {
        min(max(value.isFinite ? value : 1, 0.05), 1)
    }
}
