import CoreGraphics
import Foundation

struct TikZCoordinateMapper {
    let canvasWidth: Double
    let canvasHeight: Double

    init(canvasWidth: Double = 16.0, canvasHeight: Double = 11.0) {
        self.canvasWidth = canvasWidth
        self.canvasHeight = canvasHeight
    }

    func map(_ point: CGPoint, in size: CGSize) -> CGPoint {
        guard size.width > 0, size.height > 0 else { return .zero }
        let x = max(0, min(1, point.x / size.width)) * canvasWidth
        let y = (1 - max(0, min(1, point.y / size.height))) * canvasHeight
        return CGPoint(x: x, y: y)
    }

    func format(_ point: CGPoint) -> String {
        "(\(number(point.x)),\(number(point.y)))"
    }

    func number(_ value: Double) -> String {
        String(format: "%.3f", value)
            .replacingOccurrences(of: #"0+$"#, with: "", options: .regularExpression)
            .replacingOccurrences(of: #"\.$"#, with: "", options: .regularExpression)
    }
}
