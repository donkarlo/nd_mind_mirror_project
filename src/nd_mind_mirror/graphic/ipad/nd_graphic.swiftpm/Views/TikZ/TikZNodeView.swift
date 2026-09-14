// Passive TikZ node renderer. Canvas interaction is owned by the centralized UIKit layer.

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
            labelBody
        }
        .frame(width: size.width, height: size.height)
        .position(x: center.x, y: center.y)
        .allowsHitTesting(editingLabel != nil)
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

    @ViewBuilder
    private var labelBody: some View {
        if let editingLabel {
            TextField("Label", text: editingLabel)
                .font(.caption)
                .foregroundStyle(node.textColor.color)
                .multilineTextAlignment(.center)
                .textFieldStyle(.roundedBorder)
                .padding(5)
                .onSubmit { onCommitLabel() }
        } else if !node.label.isEmpty {
            Text(node.label)
                .font(.caption)
                .foregroundStyle(node.textColor.color)
                .lineLimit(2)
                .minimumScaleFactor(0.6)
                .padding(4)
                .allowsHitTesting(false)
        }
    }
}
