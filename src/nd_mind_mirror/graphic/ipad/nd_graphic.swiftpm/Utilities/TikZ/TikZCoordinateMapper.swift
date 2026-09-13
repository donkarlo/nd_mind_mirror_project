// Convert between the fixed 16x11 TikZ canvas and SwiftUI canvas points.

import CoreGraphics
import Foundation

struct TikZCoordinateMapper {
    let canvasWidth: Double = 16
    let canvasHeight: Double = 11

    func viewPoint(for tikzPoint: CGPoint, in size: CGSize) -> CGPoint {
        CGPoint(
            x: CGFloat(Double(tikzPoint.x) / canvasWidth) * size.width,
            y: CGFloat(1 - Double(tikzPoint.y) / canvasHeight) * size.height
        )
    }

    func tikzPoint(for viewPoint: CGPoint, in size: CGSize) -> CGPoint {
        let safeWidth = max(size.width, 1)
        let safeHeight = max(size.height, 1)
        let x = min(max(Double(viewPoint.x / safeWidth) * canvasWidth, 0), canvasWidth)
        let y = min(max((1 - Double(viewPoint.y / safeHeight)) * canvasHeight, 0), canvasHeight)
        return CGPoint(x: x, y: y)
    }

    func viewSize(width: Double, height: Double, in size: CGSize) -> CGSize {
        CGSize(
            width: max(CGFloat(width / canvasWidth) * size.width, 36),
            height: max(CGFloat(height / canvasHeight) * size.height, 28)
        )
    }

    func number(_ value: Double) -> String {
        let rounded = (value * 1000).rounded() / 1000
        return String(format: "%.3f", rounded)
            .replacingOccurrences(of: #"0+$"#, with: "", options: .regularExpression)
            .replacingOccurrences(of: #"\.$"#, with: "", options: .regularExpression)
    }
}
