import UIKit

/// View-only measurement overlay with independently switchable grid and rulers.
final class MeasurementGridView: UIView {
    private static let pixelsPerCentimeter: CGFloat = 1240.0 / 21.0
    private static let halfCentimeterSpacing: CGFloat = pixelsPerCentimeter / 2.0
    private static let rulerBand: CGFloat = 30.0
    private static let minorTickLength: CGFloat = 10.0
    private static let majorTickLength: CGFloat = 18.0

    var showGrid = true {
        didSet { if oldValue != showGrid { setNeedsDisplay() } }
    }
    var showRulers = true {
        didSet { if oldValue != showRulers { setNeedsDisplay() } }
    }

    override init(frame: CGRect) {
        super.init(frame: frame)
        backgroundColor = .clear
        isOpaque = false
        isUserInteractionEnabled = false
        contentMode = .redraw
    }

    required init?(coder: NSCoder) { nil }

    override func draw(_ rect: CGRect) {
        guard let context = UIGraphicsGetCurrentContext() else { return }
        context.saveGState()
        defer { context.restoreGState() }
        let spacing = Self.halfCentimeterSpacing
        guard spacing > 0 else { return }
        if showGrid { drawGrid(in: context, spacing: spacing) }
        if showRulers { drawRulers(in: context, spacing: spacing) }
    }

    private func drawGrid(in context: CGContext, spacing: CGFloat) {
        var index = 0
        var x: CGFloat = 0
        while x <= bounds.width + 0.5 {
            let major = index.isMultiple(of: 2)
            context.setStrokeColor(UIColor.systemGray.withAlphaComponent(major ? 0.20 : 0.10).cgColor)
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
            context.setStrokeColor(UIColor.systemGray.withAlphaComponent(major ? 0.20 : 0.10).cgColor)
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

        context.setStrokeColor(UIColor.secondaryLabel.withAlphaComponent(0.72).cgColor)
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
            context.setStrokeColor(UIColor.label.withAlphaComponent(major ? 0.72 : 0.46).cgColor)
            context.setLineWidth(major ? 1.25 : 0.85)
            context.move(to: CGPoint(x: x, y: Self.rulerBand))
            context.addLine(to: CGPoint(x: x, y: Self.rulerBand - length))
            context.strokePath()
            if major && index > 0 {
                NSString(string: "\(index / 2)").draw(at: CGPoint(x: x + 3, y: 3), withAttributes: textAttributes)
            }
            index += 1
            x = CGFloat(index) * spacing
        }

        index = 0
        var y: CGFloat = 0
        while y <= bounds.height + 0.5 {
            let major = index.isMultiple(of: 2)
            let length = major ? Self.majorTickLength : Self.minorTickLength
            context.setStrokeColor(UIColor.label.withAlphaComponent(major ? 0.72 : 0.46).cgColor)
            context.setLineWidth(major ? 1.25 : 0.85)
            context.move(to: CGPoint(x: Self.rulerBand, y: y))
            context.addLine(to: CGPoint(x: Self.rulerBand - length, y: y))
            context.strokePath()
            if major && index > 0 {
                NSString(string: "\(index / 2)").draw(at: CGPoint(x: 3, y: y + 2), withAttributes: textAttributes)
            }
            index += 1
            y = CGFloat(index) * spacing
        }
    }
}
