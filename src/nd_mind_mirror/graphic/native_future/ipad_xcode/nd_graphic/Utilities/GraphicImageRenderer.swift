import PencilKit
import UIKit

enum GraphicImageRenderer {
    static func pngData(
        drawing: PKDrawing,
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
            drawing.image(from: rect, scale: scale).draw(in: rect)
        }
        return image.pngData()
    }
}
