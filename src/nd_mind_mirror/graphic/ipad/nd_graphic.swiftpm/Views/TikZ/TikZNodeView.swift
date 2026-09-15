// Passive TikZ node renderer with a floating label editor above the canvas.

import SwiftUI

struct TikZNodeView: View {
    let node: TikZNode
    let canvasSize: CGSize
    let editingLabel: Binding<String>?
    let onCommitLabel: () -> Void

    private let mapper = TikZCoordinateMapper()

    var body: some View {
        let center = mapper.viewPoint(for: node.position, in: canvasSize)
        let size = mapper.viewSize(width: node.width, height: node.height, in: canvasSize)

        ZStack {
            shapeBody
                .frame(width: size.width, height: size.height)
                .position(x: center.x, y: center.y)
                .allowsHitTesting(false)

            let label = editingLabel?.wrappedValue ?? node.label
            if !label.isEmpty {
                Text(label)
                    .font(.caption)
                    .foregroundStyle(node.textColor.color)
                    .lineLimit(2)
                    .minimumScaleFactor(0.6)
                    .padding(4)
                    .frame(width: size.width, height: size.height)
                    .position(x: center.x, y: center.y)
                    .allowsHitTesting(false)
            }

            if let editingLabel {
                TikZFloatingLabelEditor(
                    text: editingLabel,
                    title: "Node label — \(node.name)",
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

    @ViewBuilder
    private var shapeBody: some View {
        if node.shape == .ellipse {
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
