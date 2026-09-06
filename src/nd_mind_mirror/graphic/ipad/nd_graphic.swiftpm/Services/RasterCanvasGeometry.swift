import UIKit

/// Maps raster images into logical canvas coordinates without changing their aspect ratio.
final class RasterCanvasGeometry {
    func aspectFitRect(imageSize: CGSize, canvasSize: CGSize) -> CGRect {
        guard imageSize.width > 0,
              imageSize.height > 0,
              canvasSize.width > 0,
              canvasSize.height > 0 else {
            return CGRect(origin: .zero, size: canvasSize)
        }

        let scale = min(
            canvasSize.width / imageSize.width,
            canvasSize.height / imageSize.height
        )
        let size = CGSize(
            width: imageSize.width * scale,
            height: imageSize.height * scale
        )
        return CGRect(
            x: (canvasSize.width - size.width) / 2,
            y: (canvasSize.height - size.height) / 2,
            width: size.width,
            height: size.height
        )
    }

    func normalizedImage(_ image: UIImage, canvasSize: CGSize) -> UIImage? {
        guard canvasSize.width > 0, canvasSize.height > 0 else { return nil }
        let format = UIGraphicsImageRendererFormat.default()
        format.scale = 1
        format.opaque = false
        return UIGraphicsImageRenderer(size: canvasSize, format: format).image { _ in
            image.draw(in: aspectFitRect(imageSize: image.size, canvasSize: canvasSize))
        }
    }
}
