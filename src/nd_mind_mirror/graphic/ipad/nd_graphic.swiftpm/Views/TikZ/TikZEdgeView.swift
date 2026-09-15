// Passive connector renderer with visual selection and a floating label editor.

import SwiftUI

struct TikZEdgeView: View {
    let edge: TikZEdge
    let sourceNode: TikZNode
    let targetNode: TikZNode
    let canvasSize: CGSize
    let selected: Bool
    let editingLabel: Binding<String>?
    let onCommitLabel: () -> Void

    private let geometry = TikZEdgePathGeometry()

    var body: some View {
        let route = geometry.route(
            for: edge,
            sourceNode: sourceNode,
            targetNode: targetNode,
            in: canvasSize
        )

        ZStack {
            if selected {
                connectorPath(route)
                    .stroke(
                        Color.accentColor.opacity(0.35),
                        style: StrokeStyle(
                            lineWidth: max(CGFloat(edge.lineWidth) + 6, 7),
                            lineCap: .round,
                            lineJoin: .round
                        )
                    )
                    .allowsHitTesting(false)
            }

            connectorPath(route)
                .stroke(
                    edge.strokeColor.color,
                    style: connectorStrokeStyle
                )
                .allowsHitTesting(false)

            if edge.directed {
                arrowHeadBody(
                    from: route.arrowDirectionStart,
                    to: route.end
                )
                .allowsHitTesting(false)
            }

            let label = editingLabel?.wrappedValue ?? edge.label
            if !label.isEmpty {
                Text(label)
                    .font(.caption2)
                    .foregroundStyle(edge.textColor.color)
                    .padding(.horizontal, 4)
                    .padding(.vertical, 2)
                    .background(
                        .thinMaterial,
                        in: RoundedRectangle(cornerRadius: 4)
                    )
                    .position(route.labelPoint)
                    .allowsHitTesting(false)
            }

            if let editingLabel {
                TikZFloatingLabelEditor(
                    text: editingLabel,
                    title: "Connector label",
                    onCommit: onCommitLabel
                )
                .position(
                    x: canvasSize.width / 2,
                    y: 36
                )
                .zIndex(100)
            }
        }
        .frame(
            width: canvasSize.width,
            height: canvasSize.height
        )
    }

    private var connectorStrokeStyle: StrokeStyle {
        StrokeStyle(
            lineWidth: max(CGFloat(edge.lineWidth), 0.8),
            lineCap: .round,
            lineJoin: .round,
            dash: edge.linePattern == .dashed ? [10, 7] : []
        )
    }

    private func connectorPath(_ route: TikZEdgeRoute) -> Path {
        var path = Path()
        path.move(to: route.start)

        switch edge.geometry.kind {
        case .straight:
            path.addLine(to: route.end)
        case .curve:
            if let first = route.firstControl,
               let second = route.secondControl {
                path.addCurve(
                    to: route.end,
                    control1: first,
                    control2: second
                )
            } else {
                path.addLine(to: route.end)
            }
        case .polyline:
            for point in route.bendPoints {
                path.addLine(to: point)
            }
            path.addLine(to: route.end)
        }

        return path
    }

    @ViewBuilder
    private func arrowHeadBody(
        from start: CGPoint,
        to end: CGPoint
    ) -> some View {
        if edge.arrowHeadStyle == .open {
            triangleArrowHead(from: start, to: end)
                .stroke(
                    edge.strokeColor.color,
                    style: StrokeStyle(
                        lineWidth: max(CGFloat(edge.lineWidth), 0.8),
                        lineCap: .round,
                        lineJoin: .round
                    )
                )
        } else {
            triangleArrowHead(from: start, to: end)
                .fill(edge.strokeColor.color)
        }
    }

    private func triangleArrowHead(
        from start: CGPoint,
        to end: CGPoint
    ) -> Path {
        let points = arrowWingPoints(from: start, to: end)
        var path = Path()
        path.move(to: end)
        path.addLine(to: points.left)
        path.addLine(to: points.right)
        path.closeSubpath()
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
