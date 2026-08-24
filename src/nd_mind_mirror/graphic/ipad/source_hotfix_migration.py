"""Final idempotent iPad source fixes that must run after the legacy migration layer."""

from __future__ import annotations

from pathlib import Path


class IpadSourceHotfixMigration:
    """Apply current iPad behavior fixes without replacing the whole Swift package."""

    def __init__(self, source_root: str | Path) -> None:
        self.source_root = Path(source_root).expanduser().resolve()

    def apply(self) -> bool:
        changed = False
        changed |= self._ensure_visible_measurement_grid()
        changed |= self._preserve_canvas_content_on_resize()
        changed |= self._update_ruler_help()
        return changed

    @staticmethod
    def _write_if_changed(path: Path, original: str, updated: str) -> bool:
        if updated == original:
            return False
        path.write_text(updated, encoding="utf-8")
        return True

    def _ensure_visible_measurement_grid(self) -> bool:
        """Reapply the current visible grid/ruler after the older migration layer runs."""
        path = self.source_root / "Views" / "MeasurementGridView.swift"
        desired = '''import UIKit

/// View-only A4 measurement grid plus clearly visible top and left rulers.
final class MeasurementGridView: UIView {
    /// A4 portrait is 21 cm wide; the app's A4 preset is 1240 px wide.
    private static let pixelsPerCentimeter: CGFloat = 1240.0 / 21.0
    private static let halfCentimeterSpacing: CGFloat = pixelsPerCentimeter / 2.0
    private static let rulerBand: CGFloat = 30.0
    private static let minorTickLength: CGFloat = 10.0
    private static let majorTickLength: CGFloat = 18.0

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

        let spacing = Self.halfCentimeterSpacing
        guard spacing > 0 else { return }

        drawGrid(in: context, spacing: spacing)
        drawRulers(in: context, spacing: spacing)
    }

    private func drawGrid(in context: CGContext, spacing: CGFloat) {
        var index = 0
        var x: CGFloat = 0
        while x <= bounds.width + 0.5 {
            let major = index.isMultiple(of: 2)
            context.setStrokeColor(
                UIColor.systemGray.withAlphaComponent(major ? 0.20 : 0.10).cgColor
            )
            context.setLineWidth(major ? 0.95 : 0.55)
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
                UIColor.systemGray.withAlphaComponent(major ? 0.20 : 0.10).cgColor
            )
            context.setLineWidth(major ? 0.95 : 0.55)
            context.move(to: CGPoint(x: 0, y: y))
            context.addLine(to: CGPoint(x: bounds.width, y: y))
            context.strokePath()
            index += 1
            y = CGFloat(index) * spacing
        }
    }

    private func drawRulers(in context: CGContext, spacing: CGFloat) {
        let bandColor = UIColor.systemGray6.withAlphaComponent(0.88)
        context.setFillColor(bandColor.cgColor)
        context.fill(CGRect(x: 0, y: 0, width: bounds.width, height: Self.rulerBand))
        context.fill(CGRect(x: 0, y: 0, width: Self.rulerBand, height: bounds.height))

        let edgeColor = UIColor.secondaryLabel.withAlphaComponent(0.72).cgColor
        context.setStrokeColor(edgeColor)
        context.setLineWidth(1.25)
        context.move(to: CGPoint(x: 0, y: Self.rulerBand))
        context.addLine(to: CGPoint(x: bounds.width, y: Self.rulerBand))
        context.move(to: CGPoint(x: Self.rulerBand, y: 0))
        context.addLine(to: CGPoint(x: Self.rulerBand, y: bounds.height))
        context.strokePath()

        let textAttributes: [NSAttributedString.Key: Any] = [
            .font: UIFont.monospacedDigitSystemFont(ofSize: 11, weight: .medium),
            .foregroundColor: UIColor.secondaryLabel.withAlphaComponent(0.92),
        ]

        var index = 0
        var x: CGFloat = 0
        while x <= bounds.width + 0.5 {
            let major = index.isMultiple(of: 2)
            let length = major ? Self.majorTickLength : Self.minorTickLength
            context.setStrokeColor(
                UIColor.label.withAlphaComponent(major ? 0.72 : 0.46).cgColor
            )
            context.setLineWidth(major ? 1.25 : 0.85)
            context.move(to: CGPoint(x: x, y: Self.rulerBand))
            context.addLine(to: CGPoint(x: x, y: Self.rulerBand - length))
            context.strokePath()

            if major && index > 0 {
                let centimeter = index / 2
                NSString(string: "\(centimeter)").draw(
                    at: CGPoint(x: x + 3, y: 3),
                    withAttributes: textAttributes
                )
            }
            index += 1
            x = CGFloat(index) * spacing
        }

        index = 0
        var y: CGFloat = 0
        while y <= bounds.height + 0.5 {
            let major = index.isMultiple(of: 2)
            let length = major ? Self.majorTickLength : Self.minorTickLength
            context.setStrokeColor(
                UIColor.label.withAlphaComponent(major ? 0.72 : 0.46).cgColor
            )
            context.setLineWidth(major ? 1.25 : 0.85)
            context.move(to: CGPoint(x: Self.rulerBand, y: y))
            context.addLine(to: CGPoint(x: Self.rulerBand - length, y: y))
            context.strokePath()

            if major && index > 0 {
                let centimeter = index / 2
                NSString(string: "\(centimeter)").draw(
                    at: CGPoint(x: 3, y: y + 2),
                    withAttributes: textAttributes
                )
            }
            index += 1
            y = CGFloat(index) * spacing
        }
    }
}
'''
        path.parent.mkdir(parents=True, exist_ok=True)
        original = path.read_text(encoding="utf-8") if path.is_file() else ""
        return self._write_if_changed(path, original, desired)

    def _preserve_canvas_content_on_resize(self) -> bool:
        """Resize geometry without forcing a document reload that can replace live strokes."""
        path = self.source_root / "Views" / "ContentView.swift"
        if not path.is_file():
            return False
        original = path.read_text(encoding="utf-8")
        updated = original

        old = """    /// Applies a bounded canvas size, refreshes the canvas token, and saves the document.
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
"""
        new = """    /// Applies a bounded canvas size without replacing the current drawing/background state.
    private func setCanvasSize(width: Double, height: Double) {
        canvasWidth = min(max(width.rounded(), 64), 8192)
        canvasHeight = min(max(height.rounded(), 64), 8192)
        canvasWidthText = String(Int(canvasWidth))
        canvasHeightText = String(Int(canvasHeight))
        bridge.save(
            drawing: localDrawing,
            backgroundImage: backgroundImage,
            logicalCanvasSize: logicalCanvasSize,
            pencil: pencil
        )
    }
"""
        if old in updated:
            updated = updated.replace(old, new, 1)
        return self._write_if_changed(path, original, updated)

    def _update_ruler_help(self) -> bool:
        path = self.source_root / "Views" / "ContentView.swift"
        if not path.is_file():
            return False
        original = path.read_text(encoding="utf-8")
        updated = original.replace(
            '.help("Show or hide the faint 0.5 cm / 1 cm top-and-left ruler ticks")',
            '.help("Show or hide the 0.5 cm grid and the top/left centimeter rulers")',
            1,
        )
        return self._write_if_changed(path, original, updated)
