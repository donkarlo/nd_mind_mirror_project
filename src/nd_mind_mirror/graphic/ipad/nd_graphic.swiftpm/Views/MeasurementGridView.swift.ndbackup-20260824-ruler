import UIKit

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
