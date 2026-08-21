import PencilKit
import UIKit

enum GraphicImageRenderer {
    static func pngData(
        drawing: PKDrawing,
        backgroundImage: UIImage? = nil,
        logicalCanvasSize: CGSize,
        scale: CGFloat = 1.0
    ) -> Data? {
        let targetSize = CGSize(
            width: max(logicalCanvasSize.width, 1),
            height: max(logicalCanvasSize.height, 1)
        )
        let rect = CGRect(origin: .zero, size: targetSize)
        let format = UIGraphicsImageRendererFormat.default()
        format.scale = scale
        format.opaque = true
        let renderer = UIGraphicsImageRenderer(size: targetSize, format: format)
        let image = renderer.image { context in
            UIColor.white.setFill()
            context.fill(rect)
            if let backgroundImage {
                backgroundImage.draw(in: aspectFitRect(imageSize: backgroundImage.size, canvas: rect))
            }
            drawing.image(from: rect, scale: scale).draw(in: rect)
        }
        return image.pngData()
    }

    private static func aspectFitRect(imageSize: CGSize, canvas: CGRect) -> CGRect {
        guard imageSize.width > 0, imageSize.height > 0 else { return canvas }
        let scale = min(canvas.width / imageSize.width, canvas.height / imageSize.height)
        let size = CGSize(width: imageSize.width * scale, height: imageSize.height * scale)
        return CGRect(
            x: canvas.midX - size.width / 2,
            y: canvas.midY - size.height / 2,
            width: size.width,
            height: size.height
        )
    }
}
