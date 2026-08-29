import UIKit

/// Builds one editable raster canvas from the base image and any legacy image objects.
final class RasterCanvasComposer {
    func flatten(
        backgroundImage: UIImage?,
        legacyImageObjects: [CanvasImageObject],
        canvasSize: CGSize
    ) -> UIImage? {
        guard backgroundImage != nil || !legacyImageObjects.isEmpty else { return nil }
        return render(canvasSize: canvasSize) { canvasRect in
            if let backgroundImage {
                backgroundImage.draw(in: aspectFitRect(imageSize: backgroundImage.size, canvasRect: canvasRect))
            }
            for object in legacyImageObjects {
                guard let image = object.image else { continue }
                let frame = object.frame.intersection(canvasRect)
                guard !frame.isNull, !frame.isEmpty else { continue }
                image.draw(in: frame)
            }
        }
    }

    func inserting(
        image: UIImage,
        into backgroundImage: UIImage?,
        canvasSize: CGSize
    ) -> UIImage? {
        guard image.size.width > 0, image.size.height > 0 else { return backgroundImage }
        return render(canvasSize: canvasSize) { canvasRect in
            if let backgroundImage {
                backgroundImage.draw(in: aspectFitRect(imageSize: backgroundImage.size, canvasRect: canvasRect))
            }
            image.draw(in: insertionFrame(imageSize: image.size, canvasRect: canvasRect))
        }
    }

    private func render(
        canvasSize: CGSize,
        drawing: (CGRect) -> Void
    ) -> UIImage? {
        let targetSize = CGSize(width: max(canvasSize.width, 1), height: max(canvasSize.height, 1))
        let format = UIGraphicsImageRendererFormat.default()
        format.scale = 1
        format.opaque = false
        let renderer = UIGraphicsImageRenderer(size: targetSize, format: format)
        return renderer.image { _ in
            drawing(CGRect(origin: .zero, size: targetSize))
        }
    }

    private func insertionFrame(imageSize: CGSize, canvasRect: CGRect) -> CGRect {
        let maximumDimension = max(
            48,
            min(600, canvasRect.width * 0.45, canvasRect.height * 0.45)
        )
        let naturalMaximum = max(imageSize.width, imageSize.height)
        let scale = min(1, maximumDimension / max(naturalMaximum, 1))
        let size = CGSize(
            width: max(24, imageSize.width * scale),
            height: max(24, imageSize.height * scale)
        )
        let origin = CGPoint(
            x: min(20, max(canvasRect.width - size.width, 0)),
            y: min(20, max(canvasRect.height - size.height, 0))
        )
        return CGRect(origin: origin, size: size).intersection(canvasRect)
    }

    private func aspectFitRect(imageSize: CGSize, canvasRect: CGRect) -> CGRect {
        guard imageSize.width > 0, imageSize.height > 0 else { return canvasRect }
        let scale = min(canvasRect.width / imageSize.width, canvasRect.height / imageSize.height)
        let size = CGSize(width: imageSize.width * scale, height: imageSize.height * scale)
        return CGRect(
            x: canvasRect.midX - size.width / 2,
            y: canvasRect.midY - size.height / 2,
            width: size.width,
            height: size.height
        )
    }
}
