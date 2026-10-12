// Passive TikZ node renderer with in-place label editing.

import SwiftUI

struct TikZNodeView: View {
    let node: TikZNode
    let canvasSize: CGSize
    let editingLabel: Binding<String>?
    let onCommitLabel: () -> Void

    private let nodeGeometry = TikZNodeGeometry()

    var body: some View {
        let rect = nodeGeometry.rect(for: node, in: canvasSize)
        let center = CGPoint(x: rect.midX, y: rect.midY)
        let size = rect.size

        ZStack {
            shapeBody
                .frame(width: size.width, height: size.height)
                .position(x: center.x, y: center.y)
                .allowsHitTesting(false)

            if let editingLabel {
                TikZInlineLabelEditor(
                    text: editingLabel,
                    textColor: node.textColor.color,
                    font: .caption,
                    width: max(size.width - 10, 44),
                    height: max(size.height - 10, 28),
                    backgroundColor: .clear,
                    onCommit: onCommitLabel
                )
                .position(x: center.x, y: center.y)
                .zIndex(20)
            } else if !node.label.isEmpty {
                Text(node.label)
                    .font(.caption)
                    .foregroundStyle(node.textColor.color)
                    .lineLimit(2)
                    .minimumScaleFactor(0.6)
                    .padding(4)
                    .frame(width: size.width, height: size.height)
                    .position(x: center.x, y: center.y)
                    .allowsHitTesting(false)
            }
        }
        .frame(
            width: canvasSize.width,
            height: canvasSize.height
        )
    }

    @ViewBuilder
    private var shapeBody: some View {
        if node.shape == .triangle {
            TikZTriangleShape()
                .fill(node.fillColor.color)
                .overlay(
                    TikZTriangleShape().stroke(
                        node.strokeColor.color,
                        lineWidth: max(CGFloat(node.lineWidth), 0.7)
                    )
                )
        } else if node.shape == .circle {
            Circle()
                .fill(node.fillColor.color)
                .overlay(
                    Circle().stroke(node.strokeColor.color, lineWidth: max(CGFloat(node.lineWidth), 0.7))
                )
        } else if node.shape == .ellipse {
            Ellipse()
                .fill(node.fillColor.color)
                .overlay(
                    Ellipse().stroke(
                        node.strokeColor.color,
                        lineWidth: max(CGFloat(node.lineWidth), 0.7)
                    )
                )
        } else {
            Rectangle()
                .fill(node.fillColor.color)
                .overlay(
                    Rectangle().stroke(
                        node.strokeColor.color,
                        lineWidth: max(CGFloat(node.lineWidth), 0.7)
                    )
                )
        }
    }
}
