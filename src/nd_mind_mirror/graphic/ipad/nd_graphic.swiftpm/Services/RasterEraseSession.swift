import UIKit

/// Maintains one mutable bitmap context for an entire Pencil erase gesture.
/// The source image is normalized to canvas coordinates once; erase samples then
/// clear pixels directly without rebuilding the full renderer for each segment.
final class RasterEraseSession {
    private let context: CGContext
    private let canvasSize: CGSize
    private var previousPoint: CGPoint?
    private(set) var didChange = false

    init?(image: UIImage, canvasSize: CGSize) {
        let width = max(Int(ceil(canvasSize.width)), 1)
        let height = max(Int(ceil(canvasSize.height)), 1)
        guard canvasSize.width > 0, canvasSize.height > 0,
              let context = CGContext(
                data: nil,
                width: width,
                height: height,
                bitsPerComponent: 8,
                bytesPerRow: 0,
                space: CGColorSpaceCreateDeviceRGB(),
                bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
              ) else { return nil }

        self.context = context
        self.canvasSize = canvasSize

        context.saveGState()
        context.translateBy(x: 0, y: CGFloat(height))
        context.scaleBy(x: CGFloat(width) / canvasSize.width, y: -CGFloat(height) / canvasSize.height)
        if let cgImage = normalizedCGImage(from: image, canvasSize: canvasSize) {
            context.draw(cgImage, in: CGRect(origin: .zero, size: canvasSize))
        }
        context.restoreGState()
    }

    /// Clears a coalesced Pencil sample batch and connects it to the previous batch.
    func erase(points: [CGPoint], brushDiameter: CGFloat) {
        guard !points.isEmpty else { return }
        let validPoints = points.filter {
            $0.x >= 0 && $0.y >= 0 && $0.x <= canvasSize.width && $0.y <= canvasSize.height
        }
        guard !validPoints.isEmpty else { return }

        let width = CGFloat(context.width)
        let height = CGFloat(context.height)
        let scaleX = width / canvasSize.width
        let scaleY = height / canvasSize.height
        let diameter = max(1, brushDiameter * max(scaleX, scaleY))

        context.saveGState()
        context.setBlendMode(.clear)
        context.setLineCap(.round)
        context.setLineJoin(.round)
        context.setLineWidth(diameter)

        let mapped = validPoints.map {
            CGPoint(x: $0.x * scaleX, y: height - ($0.y * scaleY))
        }

        if let previousPoint {
            let start = CGPoint(
                x: previousPoint.x * scaleX,
                y: height - (previousPoint.y * scaleY)
            )
            context.beginPath()
            context.move(to: start)
            for point in mapped {
                context.addLine(to: point)
            }
            context.strokePath()
        } else if let first = mapped.first {
            let radius = diameter / 2
            context.fillEllipse(in: CGRect(
                x: first.x - radius,
                y: first.y - radius,
                width: diameter,
                height: diameter
            ))
            if mapped.count > 1 {
                context.beginPath()
                context.move(to: first)
                for point in mapped.dropFirst() {
                    context.addLine(to: point)
                }
                context.strokePath()
            }
        }

        context.restoreGState()
        previousPoint = validPoints.last
        didChange = true
    }

    func image() -> UIImage? {
        guard let cgImage = context.makeImage() else { return nil }
        return UIImage(cgImage: cgImage, scale: 1, orientation: .up)
    }

    private func normalizedCGImage(from image: UIImage, canvasSize: CGSize) -> CGImage? {
        let format = UIGraphicsImageRendererFormat.default()
        format.scale = 1
        format.opaque = false
        let renderer = UIGraphicsImageRenderer(size: canvasSize, format: format)
        let normalized = renderer.image { _ in
            image.draw(in: CGRect(origin: .zero, size: canvasSize))
        }
        return normalized.cgImage
    }
}
