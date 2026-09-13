// Render the Ubuntu TikZ preview and overlay editable named nodes.

import SwiftUI

struct TikZCanvasView: View {
    let graph: TikZGraph
    let previewImage: UIImage?
    let selectedNodeName: String?
    let edgeStartNodeName: String?
    let onNodeTap: (TikZNode) -> Void
    let onNodeMove: (TikZNode, CGPoint) -> Void

    var body: some View {
        GeometryReader { proxy in
            let canvas = fittedCanvas(in: proxy.size)
            ZStack {
                Color(uiColor: .secondarySystemBackground)
                ZStack {
                    Color.white
                    if let previewImage {
                        Image(uiImage: previewImage)
                            .resizable()
                            .scaledToFit()
                            .allowsHitTesting(false)
                    }
                    ForEach(graph.nodes) { node in
                        TikZNodeView(
                            node: node,
                            canvasSize: canvas,
                            selected: selectedNodeName == node.name,
                            connecting: edgeStartNodeName == node.name,
                            onTap: { onNodeTap(node) },
                            onMove: { onNodeMove(node, $0) }
                        )
                    }
                }
                .frame(width: canvas.width, height: canvas.height)
                .clipped()
                .shadow(radius: 4, y: 2)
            }
        }
    }

    private func fittedCanvas(in size: CGSize) -> CGSize {
        let aspect = 16.0 / 11.0
        let widthFromHeight = size.height * aspect
        if widthFromHeight <= size.width {
            return CGSize(width: widthFromHeight, height: size.height)
        }
        return CGSize(width: size.width, height: size.width / aspect)
    }
}
