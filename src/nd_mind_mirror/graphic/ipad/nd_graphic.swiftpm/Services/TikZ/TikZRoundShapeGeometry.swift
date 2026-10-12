// Classify rounded TikZ nodes in displayed canvas coordinates.
// The horizontal and vertical TikZ-to-screen scales can differ.

import CoreGraphics

enum TikZRoundShapeGeometry {
    private static let circleTolerance = 0.05
    private static let mapper = TikZCoordinateMapper()

    static func shape(for size: CGSize, on canvas: CGSize) -> TikZNodeShape {
        let renderedWidth = max(
            Double(size.width) / mapper.canvasWidth * Double(canvas.width), 1
        )
        let renderedHeight = max(
            Double(size.height) / mapper.canvasHeight * Double(canvas.height), 1
        )
        let difference = abs(renderedWidth - renderedHeight)
        return difference <= max(renderedWidth, renderedHeight) * circleTolerance
            ? .circle : .ellipse
    }

    static func normalizedSize(_ size: CGSize, shape: TikZNodeShape) -> CGSize {
        guard shape == .circle else { return size }
        // Use the larger source dimension so the displayed circle fits the
        // user's dragged bounds on the more compressed screen axis.
        let diameter = max(max(size.width, size.height), 0.2)
        return CGSize(width: diameter, height: diameter)
    }
}
