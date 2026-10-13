// Compact visual sample for a saved TikZ node or connector appearance.

import SwiftUI

struct TikZStyleSampleView: View {
    let tool: TikZCanvasTool
    let nodeStyle: TikZNodeStyle
    let edgeStyle: TikZEdgeStyle

    var body: some View {
        ZStack {
            if tool.nodeShape != nil {
                nodeSample
            } else {
                edgeSample
            }
        }
        .frame(width: 42, height: 35)
        .contentShape(Rectangle())
    }

    @ViewBuilder
    private var nodeSample: some View {
        let color = nodeStyle.strokeColor.color
        let width = max(CGFloat(nodeStyle.lineWidth), 1)
        if tool == .triangle {
            TikZTriangleShape()
                .fill(nodeStyle.fillColor.color)
                .overlay(TikZTriangleShape().stroke(color, lineWidth: width))
                .frame(width: 31, height: 27)
                .overlay(Text("A")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(nodeStyle.textColor.color)
                    .offset(y: 3))
        } else if tool == .ellipse {
            Ellipse()
                .fill(nodeStyle.fillColor.color)
                .overlay(Ellipse().stroke(color, lineWidth: width))
                .frame(width: 33, height: 27)
                .overlay(Text("A")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(nodeStyle.textColor.color))
        } else {
            RoundedRectangle(cornerRadius: 1)
                .fill(nodeStyle.fillColor.color)
                .overlay(RoundedRectangle(cornerRadius: 1)
                    .stroke(color, lineWidth: width))
                .frame(width: 33, height: 27)
                .overlay(Text("A")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(nodeStyle.textColor.color))
        }
    }

    private var edgeSample: some View {
        ZStack {
            Path { path in
                path.move(to: CGPoint(x: 3, y: 19))
                if tool == .curveConnector {
                    path.addQuadCurve(
                        to: CGPoint(x: 38, y: 19),
                        control: CGPoint(x: 20, y: 1)
                    )
                } else if tool == .polylineConnector {
                    path.addLine(to: CGPoint(x: 19, y: 7))
                    path.addLine(to: CGPoint(x: 38, y: 19))
                } else {
                    path.addLine(to: CGPoint(x: 38, y: 19))
                }
            }
            .stroke(
                edgeStyle.strokeColor.color,
                style: StrokeStyle(
                    lineWidth: max(CGFloat(edgeStyle.lineWidth), 1.5),
                    dash: edgeStyle.linePattern == .dashed ? [4, 3] : []
                )
            )
            if edgeStyle.directed {
                Image(systemName: "arrowtriangle.right.fill")
                    .font(.system(size: 7))
                    .foregroundStyle(edgeStyle.strokeColor.color)
                    .position(x: 39, y: 19)
            }
            Text("A")
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(edgeStyle.textColor.color)
                .position(x: 20, y: 28)
        }
    }
}
