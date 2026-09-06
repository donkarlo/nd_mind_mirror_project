import UIKit

/// Collects one partial-eraser path in logical canvas coordinates and renders it once.
final class RasterEraseSession {
    private let sourceImage: UIImage
    private let canvasSize: CGSize
    private let path = UIBezierPath()
    private var brushDiameter: CGFloat = 1
    private var hasPoint = false
    private(set) var didChange = false

    init?(image: UIImage, canvasSize: CGSize) {
        guard canvasSize.width > 0,
              canvasSize.height > 0,
              let normalized = RasterCanvasGeometry().normalizedImage(
                image,
                canvasSize: canvasSize
              ) else {
            return nil
        }
        self.canvasSize = canvasSize
        self.sourceImage = normalized
        path.lineCapStyle = .round
        path.lineJoinStyle = .round
    }

    func erase(points: [CGPoint], brushDiameter: CGFloat) {
        let valid = points.filter {
            $0.x >= 0 && $0.y >= 0
                && $0.x <= canvasSize.width
                && $0.y <= canvasSize.height
        }
        guard !valid.isEmpty else { return }

        self.brushDiameter = max(1, brushDiameter)
        path.lineWidth = self.brushDiameter

        for point in valid {
            if !hasPoint {
                path.move(to: point)
                path.addLine(to: point)
                hasPoint = true
            } else {
                path.addLine(to: point)
            }
        }
        didChange = true
    }

    func makePreviewLayer() -> CAShapeLayer {
        let layer = CAShapeLayer()
        layer.frame = CGRect(origin: .zero, size: canvasSize)
        layer.fillColor = UIColor.clear.cgColor
        layer.strokeColor = UIColor.white.cgColor
        layer.lineCap = .round
        layer.lineJoin = .round
        layer.lineWidth = brushDiameter
        layer.path = path.cgPath
        return layer
    }

    func updatePreviewLayer(_ layer: CAShapeLayer) {
        layer.lineWidth = brushDiameter
        layer.path = path.cgPath
    }

    func image() -> UIImage? {
        guard didChange else { return sourceImage }
        let format = UIGraphicsImageRendererFormat.default()
        format.scale = 1
        format.opaque = false
        return UIGraphicsImageRenderer(size: canvasSize, format: format).image { rendererContext in
            sourceImage.draw(in: CGRect(origin: .zero, size: canvasSize))
            let context = rendererContext.cgContext
            context.saveGState()
            context.setBlendMode(.clear)
            context.setLineCap(.round)
            context.setLineJoin(.round)
            context.setLineWidth(brushDiameter)
            context.addPath(path.cgPath)
            context.strokePath()
            context.restoreGState()
        }
    }
}
