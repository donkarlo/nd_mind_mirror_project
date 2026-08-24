"""Idempotently migrate the editable Swift iPad source to the current feature set."""

from __future__ import annotations

from pathlib import Path


class IpadSourceMigration:
    """Apply small source transformations without replacing the user's whole Swift package."""

    _MARKER = "ND_MIND_MIRROR_IPAD_LAYOUT_20260823"

    def __init__(self, source_root: str | Path) -> None:
        self.source_root = Path(source_root).expanduser().resolve()

    def apply(self) -> bool:
        """Apply all current migrations and return whether any source file changed."""
        changed = False
        changed |= self._ensure_measurement_grid_file()
        changed |= self._migrate_graphic_message()
        changed |= self._migrate_content_view()
        changed |= self._migrate_pencil_canvas()
        return changed

    @staticmethod
    def _write_if_changed(path: Path, original: str, updated: str) -> bool:
        if updated == original:
            return False
        path.write_text(updated, encoding="utf-8")
        return True

    @staticmethod
    def _replace_once(text: str, old: str, new: str) -> str:
        if new in text:
            return text
        if old not in text:
            return text
        return text.replace(old, new, 1)

    def _ensure_measurement_grid_file(self) -> bool:
        path = self.source_root / "Views" / "MeasurementGridView.swift"
        desired = '''import UIKit

/// View-only A4 measurement grid: 0.5 cm minor lines and 1 cm major lines, without labels.
final class MeasurementGridView: UIView {
    /// A4 portrait is 21 cm wide; the app's A4 preset is 1240 px wide.
    private static let pixelsPerCentimeter: CGFloat = 1240.0 / 21.0
    private static let minorSpacing: CGFloat = pixelsPerCentimeter / 2.0

    override init(frame: CGRect) {
        super.init(frame: frame)
        backgroundColor = .clear
        isOpaque = false
        isUserInteractionEnabled = false
        contentMode = .redraw
    }

    required init?(coder: NSCoder) {
        nil
    }

    override func draw(_ rect: CGRect) {
        guard let context = UIGraphicsGetCurrentContext() else { return }
        context.saveGState()
        defer { context.restoreGState() }

        let spacing = Self.minorSpacing
        guard spacing > 0 else { return }

        var index = 0
        var x: CGFloat = 0
        while x <= bounds.width + 0.5 {
            let major = index.isMultiple(of: 2)
            context.setStrokeColor(
                UIColor.label.withAlphaComponent(major ? 0.20 : 0.10).cgColor
            )
            context.setLineWidth(major ? 0.55 : 0.32)
            context.move(to: CGPoint(x: x, y: 0))
            context.addLine(to: CGPoint(x: x, y: bounds.height))
            context.strokePath()
            index += 1
            x = CGFloat(index) * spacing
        }

        index = 0
        var y: CGFloat = 0
        while y <= bounds.height + 0.5 {
            let major = index.isMultiple(of: 2)
            context.setStrokeColor(
                UIColor.label.withAlphaComponent(major ? 0.20 : 0.10).cgColor
            )
            context.setLineWidth(major ? 0.55 : 0.32)
            context.move(to: CGPoint(x: 0, y: y))
            context.addLine(to: CGPoint(x: bounds.width, y: y))
            context.strokePath()
            index += 1
            y = CGFloat(index) * spacing
        }
    }
}
'''
        path.parent.mkdir(parents=True, exist_ok=True)
        original = path.read_text(encoding="utf-8") if path.exists() else ""
        return self._write_if_changed(path, original, desired)

    def _migrate_graphic_message(self) -> bool:
        path = self.source_root / "Models" / "GraphicMessage.swift"
        if not path.is_file():
            return False
        original = path.read_text(encoding="utf-8")
        text = original
        text = self._replace_once(
            text,
            "    var imageName: String?\n    var canvasWidth: Int?",
            "    var imageName: String?\n    var sourceName: String?\n    var canvasWidth: Int?",
        )
        text = self._replace_once(
            text,
            '        case imageName = "image_name"\n        case canvasWidth = "canvas_width"',
            '        case imageName = "image_name"\n        case sourceName = "source_name"\n        case canvasWidth = "canvas_width"',
        )
        return self._write_if_changed(path, original, text)

    def _migrate_content_view(self) -> bool:
        path = self.source_root / "Views" / "ContentView.swift"
        if not path.is_file():
            return False
        original = path.read_text(encoding="utf-8")
        text = original

        text = text.replace(
            "    @State private var canvasWidth: Double = 1600\n"
            "    @State private var canvasHeight: Double = 1000\n"
            "    @State private var canvasWidthText = \"1600\"\n"
            "    @State private var canvasHeightText = \"1000\"",
            "    @State private var canvasWidth: Double = 1240\n"
            "    @State private var canvasHeight: Double = 1754\n"
            "    @State private var canvasWidthText = \"1240\"\n"
            "    @State private var canvasHeightText = \"1754\"",
            1,
        )
        text = self._replace_once(
            text,
            "    @State private var showDiagnostics = true\n",
            "    @State private var showDiagnostics = true\n"
            "    @State private var showMeasurementGrid = true\n",
        )
        text = self._replace_once(
            text,
            "                logicalCanvasSize: logicalCanvasSize,\n"
            "                onDrawingChanged: { drawing in",
            "                logicalCanvasSize: logicalCanvasSize,\n"
            "                showMeasurementGrid: showMeasurementGrid,\n"
            "                onDrawingChanged: { drawing in",
        )
        text = text.replace(
            '                    Button("A4 portrait — 1240 × 1754") { setCanvasSize(width: 1240, height: 1754) }',
            '                    Button("A4 portrait — 21 × 29.7 cm — 1240 × 1754") { setCanvasSize(width: 1240, height: 1754) }',
            1,
        )
        status_old = '''        HStack(spacing: 14) {
            Label("\\(Int((zoomScale * 100).rounded()))%", systemImage: "magnifyingglass")
            Text("Canvas \\(Int(canvasWidth)) × \\(Int(canvasHeight)) px")
            if tool == .lasso {
'''
        status_new = '''        HStack(spacing: 12) {
            if let sourceName = bridge.document?.sourceName,
               let imageName = bridge.document?.imageName {
                Text("\\(sourceName) > \\(imageName)")
                    .font(.caption2.weight(.semibold))
                    .lineLimit(1)
                    .truncationMode(.middle)
            } else if let imageName = bridge.document?.imageName {
                Text(imageName)
                    .font(.caption2.weight(.semibold))
                    .lineLimit(1)
            }
            Label("\\(Int((zoomScale * 100).rounded()))%", systemImage: "magnifyingglass")
            Text("Canvas \\(Int(canvasWidth)) × \\(Int(canvasHeight)) px")
            Button {
                showMeasurementGrid.toggle()
            } label: {
                Label(
                    showMeasurementGrid ? "Grid" : "Grid off",
                    systemImage: showMeasurementGrid ? "grid" : "grid.circle"
                )
            }
            .buttonStyle(.bordered)
            .controlSize(.mini)
            .help("Show or hide the 1 cm / 0.5 cm A4 measurement grid")
            if tool == .lasso {
'''
        text = self._replace_once(text, status_old, status_new)
        if self._MARKER not in text:
            text = text.replace(
                "// Builds the native iPad drawing workflow, including persistent stroke settings, zoom status, recent colors, and lasso selection.\n",
                "// Builds the native iPad drawing workflow, including persistent stroke settings, zoom status, recent colors, and lasso selection.\n"
                f"// {self._MARKER}\n",
                1,
            )
        return self._write_if_changed(path, original, text)

    def _migrate_pencil_canvas(self) -> bool:
        path = self.source_root / "Views" / "PencilCanvasView.swift"
        if not path.is_file():
            return False
        original = path.read_text(encoding="utf-8")
        text = original
        text = self._replace_once(
            text,
            "    let logicalCanvasSize: CGSize\n    let onDrawingChanged: (PKDrawing) -> Void",
            "    let logicalCanvasSize: CGSize\n"
            "    let showMeasurementGrid: Bool\n"
            "    let onDrawingChanged: (PKDrawing) -> Void",
        )
        text = self._replace_once(
            text,
            "        background.image = backgroundImage\n        content.addSubview(background)\n\n        let canvas = PKCanvasView(frame: content.bounds)",
            "        background.image = backgroundImage\n"
            "        content.addSubview(background)\n\n"
            "        let measurementGrid = MeasurementGridView(frame: content.bounds)\n"
            "        measurementGrid.autoresizingMask = [.flexibleWidth, .flexibleHeight]\n"
            "        measurementGrid.isHidden = !showMeasurementGrid\n"
            "        content.addSubview(measurementGrid)\n\n"
            "        let canvas = PKCanvasView(frame: content.bounds)",
        )
        text = self._replace_once(
            text,
            "        context.coordinator.backgroundView = background\n        context.coordinator.canvas = canvas",
            "        context.coordinator.backgroundView = background\n"
            "        context.coordinator.measurementGridView = measurementGrid\n"
            "        context.coordinator.canvas = canvas",
        )
        text = self._replace_once(
            text,
            "        coordinator.backgroundView?.image = backgroundImage\n\n        let sizeChanged",
            "        coordinator.backgroundView?.image = backgroundImage\n"
            "        coordinator.measurementGridView?.isHidden = !showMeasurementGrid\n\n"
            "        let sizeChanged",
        )
        text = self._replace_once(
            text,
            "            coordinator.backgroundView?.frame = CGRect(origin: .zero, size: logicalCanvasSize)\n"
            "            coordinator.canvas?.frame = CGRect(origin: .zero, size: logicalCanvasSize)",
            "            coordinator.backgroundView?.frame = CGRect(origin: .zero, size: logicalCanvasSize)\n"
            "            coordinator.measurementGridView?.frame = CGRect(origin: .zero, size: logicalCanvasSize)\n"
            "            coordinator.canvas?.frame = CGRect(origin: .zero, size: logicalCanvasSize)",
        )
        text = self._replace_once(
            text,
            "        weak var backgroundView: UIImageView?\n        weak var selectionOverlay: SelectionResizeOverlay?",
            "        weak var backgroundView: UIImageView?\n"
            "        weak var measurementGridView: MeasurementGridView?\n"
            "        weak var selectionOverlay: SelectionResizeOverlay?",
        )
        if self._MARKER not in text:
            text = text.replace(
                "// Hosts the PencilKit canvas, viewport zoom, two-finger undo, lasso selection, and proportional selection resizing.\n",
                "// Hosts the PencilKit canvas, viewport zoom, two-finger undo, lasso selection, and proportional selection resizing.\n"
                f"// {self._MARKER}\n",
                1,
            )
        return self._write_if_changed(path, original, text)
