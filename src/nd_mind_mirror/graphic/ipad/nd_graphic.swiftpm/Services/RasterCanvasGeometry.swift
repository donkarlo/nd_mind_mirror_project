import UIKit

/// Keeps raster background pixels in the same logical canvas coordinates during resizing.
final class RasterCanvasGeometry {
    func normalizedImage(_ image: UIImage, canvasSize: CGSize) -> UIImage? {
        guard canvasSize.width > 0, canvasSize.height > 0 else { return nil }

        let format = UIGraphicsImageRendererFormat.default()
        format.scale = 1
        format.opaque = false
        return UIGraphicsImageRenderer(size: canvasSize, format: format).image { _ in
            image.draw(at: .zero)
        }
    }
}
