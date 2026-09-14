// Passive connector renderer with visual selection and inline label editing.

import SwiftUI

struct TikZEdgeView: View {
    let edge: TikZEdge
    let sourceNode: TikZNode
    let targetNode: TikZNode
    let canvasSize: CGSize
    let selected: Bool
    let editingLabel: Binding<String>?
    let onCommitLabel: () -> Void

    private let geometry = TikZNodeGeometry()

    var body: some View {
        let endpoints = geometry.connectorEndpoints(
            from: sourceNode,
            to: targetNode,
            in: canvasSize
        )
        let start = endpoints.start
        let end = endpoints.end
        let middle = CGPoint(
            x: (start.x + end.x) / 2,
            y: (start.y + end.y) / 2
        )

        ZStack {
            if selected {
                linePath(from: start, to: end)
                    .stroke(
                        Color.accentColor.opacity(0.35),
                        style: StrokeStyle(
                            lineWidth: max(CGFloat(edge.lineWidth) + 6, 7)
                        )
                    )
            }

            linePath(from: start, to: end)
                .stroke(
                    edge.strokeColor.color,
                    style: connectorStrokeStyle
                )

            if edge.directed {
                arrowHeadBody(from: start, to: end)
            }

            if let editingLabel {
                TextField("Label", text: editingLabel)
                    .font(.caption2)
                    .foregroundStyle(edge.textColor.color)
                    .textFieldStyle(.roundedBorder)
                    .frame(width: 150)
                    .position(middle)
                    .onSubmit { onCommitLabel() }
            } else if !edge.label.isEmpty {
                Text(edge.label)
                    .font(.caption2)
                    .foregroundStyle(edge.textColor.color)
                    .padding(.horizontal, 4)
                    .padding(.vertical, 2)
                    .background(
                        .thinMaterial,
                        in: RoundedRectangle(cornerRadius: 4)
                    )
                    .position(middle)
                    .allowsHitTesting(false)
            }
        }
        .allowsHitTesting(editingLabel != nil)
    }

    private var connectorStrokeStyle: StrokeStyle {
        StrokeStyle(
            lineWidth: max(CGFloat(edge.lineWidth), 0.8),
            lineCap: .round,
            lineJoin: .round,
            dash: edge.linePattern == .dashed ? [10, 7] : []
        )
    }

    @ViewBuilder
    private func arrowHeadBody(from start: CGPoint, to end: CGPoint) -> some View {
        if edge.arrowHeadStyle == .open {
            openArrowHead(from: start, to: end)
                .stroke(
                    edge.strokeColor.color,
                    style: StrokeStyle(
                        lineWidth: max(CGFloat(edge.lineWidth), 0.8),
                        lineCap: .round,
                        lineJoin: .round
                    )
                )
        } else {
            filledArrowHead(from: start, to: end)
                .fill(edge.strokeColor.color)
        }
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
