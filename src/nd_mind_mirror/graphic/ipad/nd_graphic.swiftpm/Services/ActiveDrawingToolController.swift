import PencilKit
import SwiftUI
import UIKit

/// Owns active tool state, applies selections immediately, and manages raster erasing.
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

    @Published private(set) var state = State(
        kind: .pencil,
        colorHex: "#000000",
        width: 1.5,
        opacity: 1.0,
        eraserMode: .whole,
        selectedSavedToolID: nil
    )
    @Published private(set) var isRasterEditing = false

    private weak var canvas: PKCanvasView?
    private weak var backgroundView: UIImageView?
    private weak var rasterSurfaceView: UIView?
    private var rasterGesture: PencilRasterEraserGestureRecognizer?
    private var rasterSession: RasterEraseSession?
    private var rasterStartImage: UIImage?
    private var ownsUndoGroup = false
    private var canvasSize = CGSize(width: 1240, height: 1754)
    private var backgroundImageChanged: ((UIImage?) -> Void)?
    private var undoManagerChanged: ((UndoManager?) -> Void)?

    var kind: GraphicTool { state.kind }
    var color: Color { Color(hex: state.colorHex) }
    var width: Double { state.width }
    var opacity: Double { state.opacity }
    var eraserMode: EraserMode { state.eraserMode }
    var selectedSavedToolID: UUID? { state.selectedSavedToolID }
    var pencilSettings: PencilSettings { PencilSettings(width: state.width, color: color) }

    /// Attaches to the live PencilKit canvas and to its parent raster surface.
    /// The raster recognizer deliberately lives outside PKCanvasView so both
    /// systems receive the exact same Apple Pencil stream.
    func attach(canvas: PKCanvasView, backgroundView: UIImageView) {
        let rasterSurfaceView = canvas.superview ?? canvas
        if self.rasterSurfaceView !== rasterSurfaceView {
            if let oldGesture = rasterGesture, let oldView = oldGesture.view {
                oldView.removeGestureRecognizer(oldGesture)
            }
            rasterGesture = nil
        }
        self.canvas = canvas
        self.backgroundView = backgroundView
        self.rasterSurfaceView = rasterSurfaceView
        canvas.undoManager?.levelsOfUndo = 0
        configureParentScrollView(for: canvas)
        attachRasterEraserIfNeeded(to: rasterSurfaceView)
        applyImmediately()
    }

    func bindRuntime(
        canvasSize: CGSize,
        backgroundImageChanged: @escaping (UIImage?) -> Void,
        undoManagerChanged: @escaping (UndoManager?) -> Void
    ) {
        self.canvasSize = canvasSize
        self.backgroundImageChanged = backgroundImageChanged
        self.undoManagerChanged = undoManagerChanged
        applyImmediately()
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

    func updateAppearance(color: Color? = nil, width: Double? = nil, opacity: Double? = nil) {
        var next = state
        if let color { next.colorHex = canonicalColor(color.hexRGB()) }
        if let width {
            next.width = next.kind == .eraser
                ? canonicalEraserWidth(width)
                : canonicalInkWidth(width)
        }
        if let opacity { next.opacity = canonicalOpacity(opacity) }
        next.selectedSavedToolID = nil
        setState(next)
    }

    func adoptDocumentPencil(width: Double?, colorHex: String?) {
        guard state.selectedSavedToolID == nil, state.kind != .eraser else { return }
        var next = state
        if let width { next.width = canonicalInkWidth(width) }
        if let colorHex, !colorHex.isEmpty { next.colorHex = canonicalColor(colorHex) }
        setState(next)
    }

    func isSelected(_ savedTool: SavedDrawingTool) -> Bool {
        state.selectedSavedToolID == savedTool.id
    }

    private func setState(_ next: State) {
        state = next
        applyImmediately()
    }

    private func configureParentScrollView(for canvas: PKCanvasView) {
        var parent = canvas.superview
        while let view = parent {
            if let scroll = view as? UIScrollView, scroll !== canvas {
                scroll.panGestureRecognizer.minimumNumberOfTouches = 2
                scroll.panGestureRecognizer.maximumNumberOfTouches = 2
                scroll.panGestureRecognizer.allowedTouchTypes = [NSNumber(value: UITouch.TouchType.direct.rawValue)]
                break
            }
            parent = view.superview
        }
    }

    private func applyImmediately() {
        guard let canvas else { return }
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
            let type: PKEraserTool.EraserType = state.eraserMode == .partial ? .bitmap : .vector
            canvas.tool = PKEraserTool(type, width: CGFloat(state.width))
        case .lasso:
            canvas.tool = PKLassoTool()
        }
        rasterGesture?.isEnabled = state.kind == .eraser
    }

    private func attachRasterEraserIfNeeded(to surface: UIView) {
        if let rasterGesture, rasterGesture.view === surface {
            rasterGesture.isEnabled = state.kind == .eraser
            return
        }
        let gesture = PencilRasterEraserGestureRecognizer(
            target: self,
            action: #selector(handleRasterErase(_:))
        )
        gesture.delegate = self
        gesture.isEnabled = state.kind == .eraser
        surface.addGestureRecognizer(gesture)
        rasterGesture = gesture
    }

    @objc private func handleRasterErase(_ gesture: PencilRasterEraserGestureRecognizer) {
        guard state.kind == .eraser, let backgroundView else { return }

        switch gesture.state {
        case .began:
            guard let image = backgroundView.image,
                  let session = RasterEraseSession(image: image, canvasSize: canvasSize) else { return }
            rasterStartImage = image
            rasterSession = session
            isRasterEditing = true
            beginEraseUndoGroup()
            applyRaster(points: gesture.currentPoints)
        case .changed:
            applyRaster(points: gesture.currentPoints)
        case .ended:
            applyRaster(points: gesture.currentPoints)
            finishRasterErase(commit: true)
        case .cancelled, .failed:
            finishRasterErase(commit: false)
        default:
            break
        }
    }

    private func applyRaster(points: [CGPoint]) {
        guard let session = rasterSession, let backgroundView else { return }
        session.erase(points: points, brushDiameter: max(2, CGFloat(state.width)))
        if session.didChange, let preview = session.image() {
            backgroundView.image = preview
        }
    }

    private func finishRasterErase(commit: Bool) {
        guard let backgroundView else {
            clearRasterSession()
            endEraseUndoGroup()
            return
        }

        let original = rasterStartImage
        let final = rasterSession?.image()
        let changed = rasterSession?.didChange == true

        if commit, changed {
            backgroundView.image = final
            registerRasterUndo(original: original, final: final)
            backgroundImageChanged?(final)
        } else {
            backgroundView.image = original
        }

        clearRasterSession()
        endEraseUndoGroup()
    }

    private func beginEraseUndoGroup() {
        guard let manager = canvas?.undoManager else { return }
        manager.levelsOfUndo = 0
        guard manager.groupingLevel == 0 else { return }
        manager.beginUndoGrouping()
        ownsUndoGroup = true
    }

    private func endEraseUndoGroup() {
        guard ownsUndoGroup, let manager = canvas?.undoManager else {
            ownsUndoGroup = false
            return
        }
        ownsUndoGroup = false
        // PencilKit may finish registering its eraser undo later in this same
        // event turn. Closing on the next main turn keeps raster + stroke erase
        // together as one Undo operation.
        DispatchQueue.main.async {
            if manager.groupingLevel > 0 {
                manager.endUndoGrouping()
                manager.setActionName("Erase")
            }
        }
    }

    private func registerRasterUndo(original: UIImage?, final: UIImage?) {
        guard let manager = canvas?.undoManager else { return }
        manager.levelsOfUndo = 0
        manager.registerUndo(withTarget: self) { target in
            target.restoreRasterImage(original, reciprocal: final)
        }
        undoManagerChanged?(manager)
    }

    private func restoreRasterImage(_ image: UIImage?, reciprocal: UIImage?) {
        guard let backgroundView else { return }
        backgroundView.image = image
        backgroundImageChanged?(image)
        if let manager = canvas?.undoManager {
            manager.levelsOfUndo = 0
            manager.registerUndo(withTarget: self) { target in
                target.restoreRasterImage(reciprocal, reciprocal: image)
            }
            manager.setActionName("Erase Image")
            undoManagerChanged?(manager)
        }
    }

    func gestureRecognizer(
        _ gestureRecognizer: UIGestureRecognizer,
        shouldRecognizeSimultaneouslyWith otherGestureRecognizer: UIGestureRecognizer
    ) -> Bool {
        gestureRecognizer === rasterGesture || otherGestureRecognizer === rasterGesture
    }

    private func clearRasterSession() {
        rasterSession = nil
        rasterStartImage = nil
        isRasterEditing = false
    }

    private func canonicalColor(_ raw: String) -> String {
        var value = raw.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
        if value.hasPrefix("#") { value.removeFirst() }
        if value.count == 8 { value = String(value.prefix(6)) }
        guard value.count == 6, value.allSatisfy(\.isHexDigit) else { return "#000000" }
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
