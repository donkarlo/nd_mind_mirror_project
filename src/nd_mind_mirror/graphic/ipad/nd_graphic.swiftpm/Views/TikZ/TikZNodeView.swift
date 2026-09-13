// Draggable visual hit target for one named TikZ node.

import SwiftUI

struct TikZNodeView: View {
    let node: TikZNode
    let canvasSize: CGSize
    let selected: Bool
    let connecting: Bool
    let onTap: () -> Void
    let onMove: (CGPoint) -> Void

    @State private var dragTranslation: CGSize = .zero
    private let mapper = TikZCoordinateMapper()

    var body: some View {
        let center = mapper.viewPoint(for: node.position, in: canvasSize)
        let size = mapper.viewSize(width: node.width, height: node.height, in: canvasSize)
        Group {
            if node.shape == .ellipse {
                Ellipse().fill(Color.clear).overlay(Ellipse().stroke(strokeColor, lineWidth: selected ? 3 : 1.5))
            } else {
                RoundedRectangle(cornerRadius: 5).fill(Color.clear).overlay(RoundedRectangle(cornerRadius: 5).stroke(strokeColor, lineWidth: selected ? 3 : 1.5))
            }
        }
        .frame(width: size.width, height: size.height)
        .contentShape(Rectangle())
        .position(x: center.x + dragTranslation.width, y: center.y + dragTranslation.height)
        .onTapGesture { onTap() }
        .gesture(
            DragGesture(minimumDistance: 2)
                .onChanged { dragTranslation = $0.translation }
                .onEnded { value in
                    let moved = CGPoint(x: center.x + value.translation.width, y: center.y + value.translation.height)
                    dragTranslation = .zero
                    onMove(mapper.tikzPoint(for: moved, in: canvasSize))
                }
        )
    }

    private var strokeColor: Color {
        if connecting { return .orange }
        return selected ? .blue : .clear
    }
}
