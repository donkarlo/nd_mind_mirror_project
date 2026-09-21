// Passive connection-point markers rendered exactly on a TikZ node perimeter.

import SwiftUI

struct TikZConnectionPointOverlay: View {
    let node: TikZNode
    let count: Int
    let canvasSize: CGSize

    private let geometry = TikZConnectionPointGeometry()
    private let diameter: CGFloat = 8

    var body: some View {
        ZStack {
            ForEach(Array(points.enumerated()), id: \.offset) { _, point in
                Circle()
                    .fill(Color.white)
                    .overlay(Circle().stroke(Color.accentColor, lineWidth: 1.5))
                    .frame(width: diameter, height: diameter)
                    .position(point)
            }
        }
        .frame(width: canvasSize.width, height: canvasSize.height)
        .allowsHitTesting(false)
    }

    private var points: [CGPoint] {
        geometry.points(
            for: node,
            count: count,
            in: canvasSize
        )
    }
}
