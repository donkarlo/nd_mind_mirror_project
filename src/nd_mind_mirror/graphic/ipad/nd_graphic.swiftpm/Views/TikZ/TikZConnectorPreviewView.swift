// Live Pencil connector preview driven by the Select-mode interaction layer.

import SwiftUI

struct TikZConnectorPreviewView: View {
    let sourceNode: TikZNode
    let currentPoint: CGPoint
    let canvasSize: CGSize
    let style: TikZEdgeStyle

    private let geometry = TikZNodeGeometry()

    var body: some View {
        let start = geometry.boundaryPoint(
            for: sourceNode,
            toward: currentPoint,
            in: canvasSize
        )

        ZStack {
            linePath(from: start, to: currentPoint)
                .stroke(
                    style.strokeColor.color.opacity(0.75),
                    style: StrokeStyle(
                        lineWidth: max(CGFloat(style.lineWidth), 1),
                        dash: style.linePattern == .dashed ? [10, 7] : []
                    )
                )

            if style.directed {
                if style.arrowHeadStyle == .open {
                    openArrowHead(from: start, to: currentPoint)
                        .stroke(
                            style.strokeColor.color.opacity(0.85),
                            lineWidth: max(CGFloat(style.lineWidth), 1)
                        )
                } else {
                    filledArrowHead(from: start, to: currentPoint)
                        .fill(style.strokeColor.color.opacity(0.85))
                }
            }
        }
        .allowsHitTesting(false)
    }

    private func linePath(from start: CGPoint, to end: CGPoint) -> Path {
        var path = Path()
        path.move(to: start)
        path.addLine(to: end)
        return path
    }

    private func filledArrowHead(from start: CGPoint, to end: CGPoint) -> Path {
        let points = arrowWingPoints(from: start, to: end)
        var path = Path()
        path.move(to: end)
        path.addLine(to: points.left)
        path.addLine(to: points.right)
        path.closeSubpath()
        return path
    }

    private func openArrowHead(from start: CGPoint, to end: CGPoint) -> Path {
        let points = arrowWingPoints(from: start, to: end)
        var path = Path()
        path.move(to: points.left)
        path.addLine(to: end)
        path.addLine(to: points.right)
        return path
    }

    private func arrowWingPoints(
        from start: CGPoint,
        to end: CGPoint
    ) -> (left: CGPoint, right: CGPoint) {
        let dx = end.x - start.x
        let dy = end.y - start.y
        let length = max(sqrt(dx * dx + dy * dy), 1)
        let ux = dx / length
        let uy = dy / length
        let size: CGFloat = 10
        let base = CGPoint(
            x: end.x - ux * size,
            y: end.y - uy * size
        )
        let px = -uy
        let py = ux
        return (
            CGPoint(
                x: base.x + px * size * 0.45,
                y: base.y + py * size * 0.45
            ),
            CGPoint(
                x: base.x - px * size * 0.45,
                y: base.y - py * size * 0.45
            )
        )
    }
}
