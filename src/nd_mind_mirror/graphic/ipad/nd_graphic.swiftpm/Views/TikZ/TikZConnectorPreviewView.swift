// Live connector preview while dragging from a source node.

import SwiftUI

struct TikZConnectorPreviewView: View {
    let sourceNode: TikZNode
    let currentPoint: CGPoint
    let canvasSize: CGSize
    let style: TikZEdgeStyle
    let kind: TikZConnectorKind

    private let nodeGeometry = TikZNodeGeometry()
    private let mapper = TikZCoordinateMapper()

    var body: some View {
        let sourceCenter = mapper.viewPoint(
            for: sourceNode.position,
            in: canvasSize
        )
        let start = nodeGeometry.boundaryPoint(
            for: sourceNode,
            toward: currentPoint,
            in: canvasSize
        )

        ZStack {
            previewPath(
                start: start,
                sourceCenter: sourceCenter,
                end: currentPoint
            )
            .stroke(
                style.strokeColor.color.opacity(0.75),
                style: StrokeStyle(
                    lineWidth: max(CGFloat(style.lineWidth), 0.8),
                    lineCap: .round,
                    lineJoin: .round,
                    dash: style.linePattern == .dashed ? [10, 7] : []
                )
            )

            if style.directed {
                let directionStart = previewDirectionStart(
                    start: start,
                    sourceCenter: sourceCenter,
                    end: currentPoint
                )
                arrowHead(
                    from: directionStart,
                    to: currentPoint
                )
            }
        }
        .allowsHitTesting(false)
    }

    private func previewPath(
        start: CGPoint,
        sourceCenter: CGPoint,
        end: CGPoint
    ) -> Path {
        var path = Path()
        path.move(to: start)

        if kind == .curve {
            let controls = curveControls(
                from: sourceCenter,
                to: end
            )
            path.addCurve(
                to: end,
                control1: controls.first,
                control2: controls.second
            )
        } else {
            path.addLine(to: end)
        }

        return path
    }

    private func previewDirectionStart(
        start: CGPoint,
        sourceCenter: CGPoint,
        end: CGPoint
    ) -> CGPoint {
        guard kind == .curve else {
            return start
        }
        return curveControls(
            from: sourceCenter,
            to: end
        ).second
    }

    private func curveControls(
        from start: CGPoint,
        to end: CGPoint
    ) -> (first: CGPoint, second: CGPoint) {
        let dx = end.x - start.x
        let dy = end.y - start.y
        let length = max(hypot(dx, dy), 1)
        let px = -dy / length
        let py = dx / length
        let lift = min(max(length * 0.18, 26), 70)

        return (
            CGPoint(
                x: start.x + dx / 3 + px * lift,
                y: start.y + dy / 3 + py * lift
            ),
            CGPoint(
                x: start.x + dx * 2 / 3 + px * lift,
                y: start.y + dy * 2 / 3 + py * lift
            )
        )
    }

    @ViewBuilder
    private func arrowHead(
        from start: CGPoint,
        to end: CGPoint
    ) -> some View {
        let triangle = triangleArrowHead(
            from: start,
            to: end
        )

        if style.arrowHeadStyle == .open {
            triangle.stroke(
                style.strokeColor.color.opacity(0.75),
                style: StrokeStyle(
                    lineWidth: max(CGFloat(style.lineWidth), 0.8),
                    lineCap: .round,
                    lineJoin: .round
                )
            )
        } else {
            triangle.fill(
                style.strokeColor.color.opacity(0.75)
            )
        }
    }

    private func triangleArrowHead(
        from start: CGPoint,
        to end: CGPoint
    ) -> Path {
        let dx = end.x - start.x
        let dy = end.y - start.y
        let length = max(hypot(dx, dy), 1)
        let ux = dx / length
        let uy = dy / length
        let size: CGFloat = 10
        let base = CGPoint(
            x: end.x - ux * size,
            y: end.y - uy * size
        )
        let px = -uy
        let py = ux

        var path = Path()
        path.move(to: end)
        path.addLine(
            to: CGPoint(
                x: base.x + px * size * 0.45,
                y: base.y + py * size * 0.45
            )
        )
        path.addLine(
            to: CGPoint(
                x: base.x - px * size * 0.45,
                y: base.y - py * size * 0.45
            )
        )
        path.closeSubpath()
        return path
    }
}
