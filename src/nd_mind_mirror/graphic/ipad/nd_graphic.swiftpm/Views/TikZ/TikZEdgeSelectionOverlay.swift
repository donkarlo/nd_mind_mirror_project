// Direct manipulation handles for curve controls and polyline bend points.

import SwiftUI

struct TikZEdgeSelectionOverlay: View {
    let edge: TikZEdge
    let sourceNode: TikZNode
    let targetNode: TikZNode
    let canvasSize: CGSize
    let onCurveControlMove: (Int, CGPoint) -> Void
    let onBendMove: (Int, CGPoint) -> Void
    let onBendRemove: (Int) -> Void

    private let mapper = TikZCoordinateMapper()
    private let pathGeometry = TikZEdgePathGeometry()

    var body: some View {
        let route = pathGeometry.route(
            for: edge,
            sourceNode: sourceNode,
            targetNode: targetNode,
            in: canvasSize
        )

        ZStack {
            if edge.geometry.kind == .curve {
                curveControls(route)
            } else if edge.geometry.kind == .polyline {
                bendControls(route)
            }
        }
    }

    @ViewBuilder
    private func curveControls(
        _ route: TikZEdgeRoute
    ) -> some View {
        if let first = route.firstControl,
           let second = route.secondControl {
            handleGuide(from: route.start, to: first)
            handleGuide(from: route.end, to: second)

            draggableHandle(
                at: first,
                accessibilityLabel: "Start curve control"
            ) { point in
                onCurveControlMove(
                    0,
                    mapper.tikzPoint(
                        for: point,
                        in: canvasSize
                    )
                )
            }

            draggableHandle(
                at: second,
                accessibilityLabel: "End curve control"
            ) { point in
                onCurveControlMove(
                    1,
                    mapper.tikzPoint(
                        for: point,
                        in: canvasSize
                    )
                )
            }
        }
    }

    @ViewBuilder
    private func bendControls(
        _ route: TikZEdgeRoute
    ) -> some View {
        ForEach(
            Array(route.bendPoints.enumerated()),
            id: \.offset
        ) { index, point in
            Circle()
                .fill(Color.accentColor)
                .overlay(
                    Circle()
                        .stroke(.white, lineWidth: 2)
                )
                .frame(width: 18, height: 18)
                .contentShape(
                    Circle()
                        .inset(by: -8)
                )
                .position(point)
                .gesture(
                    DragGesture(
                        minimumDistance: 0,
                        coordinateSpace: .named(
                            TikZCanvasView
                                .coordinateSpaceName
                        )
                    )
                    .onChanged { value in
                        onBendMove(
                            index,
                            mapper.tikzPoint(
                                for: value.location,
                                in: canvasSize
                            )
                        )
                    }
                )
                .contextMenu {
                    Button(
                        role: .destructive
                    ) {
                        onBendRemove(index)
                    } label: {
                        Label(
                            "Remove bend point",
                            systemImage: "trash"
                        )
                    }
                }
                .accessibilityLabel(
                    "Polyline bend point \(index + 1)"
                )
        }
    }

    private func handleGuide(
        from start: CGPoint,
        to end: CGPoint
    ) -> some View {
        Path { path in
            path.move(to: start)
            path.addLine(to: end)
        }
        .stroke(
            Color.accentColor.opacity(0.6),
            style: StrokeStyle(
                lineWidth: 1,
                dash: [5, 4]
            )
        )
        .allowsHitTesting(false)
    }

    private func draggableHandle(
        at point: CGPoint,
        accessibilityLabel: String,
        onMove: @escaping (CGPoint) -> Void
    ) -> some View {
        Circle()
            .fill(Color.accentColor)
            .overlay(
                Circle()
                    .stroke(.white, lineWidth: 2)
            )
            .frame(width: 20, height: 20)
            .contentShape(
                Circle()
                    .inset(by: -8)
            )
            .position(point)
            .gesture(
                DragGesture(
                    minimumDistance: 0,
                    coordinateSpace: .named(
                        TikZCanvasView
                            .coordinateSpaceName
                    )
                )
                .onChanged { value in
                    onMove(value.location)
                }
            )
            .accessibilityLabel(
                accessibilityLabel
            )
    }
}
