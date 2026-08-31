import SwiftUI

/// Places measurement rulers outside the logical canvas so they never cover image pixels.
struct MeasurementRulerFrameView<Content: View>: View {
    let isVisible: Bool
    let zoomScale: CGFloat
    let content: Content

    private let thickness: CGFloat = 28
    private let pixelsPerCentimeter: CGFloat = 1240.0 / 21.0

    init(isVisible: Bool, zoomScale: CGFloat, @ViewBuilder content: () -> Content) {
        self.isVisible = isVisible
        self.zoomScale = zoomScale
        self.content = content()
    }

    var body: some View {
        HStack(spacing: 0) {
            if isVisible {
                verticalRuler
                    .frame(width: thickness)
            }
            VStack(spacing: 0) {
                if isVisible {
                    horizontalRuler
                        .frame(height: thickness)
                }
                content
            }
        }
    }

    private var horizontalRuler: some View {
        Canvas { context, size in
            let spacing = max(pixelsPerCentimeter * max(zoomScale, 0.05), 8)
            var x: CGFloat = 0
            var index = 0
            while x <= size.width + 0.5 {
                let major = index.isMultiple(of: 1)
                var path = Path()
                path.move(to: CGPoint(x: x, y: size.height))
                path.addLine(to: CGPoint(x: x, y: size.height - (major ? 13 : 8)))
                context.stroke(path, with: .foreground, lineWidth: 1)
                if index > 0 {
                    context.draw(Text("\(index)").font(.system(size: 9, design: .monospaced)), at: CGPoint(x: x + 8, y: 8))
                }
                index += 1
                x = CGFloat(index) * spacing
            }
        }
        .background(.thinMaterial)
    }

    private var verticalRuler: some View {
        Canvas { context, size in
            let spacing = max(pixelsPerCentimeter * max(zoomScale, 0.05), 8)
            var y: CGFloat = 0
            var index = 0
            while y <= size.height + 0.5 {
                var path = Path()
                path.move(to: CGPoint(x: size.width, y: y))
                path.addLine(to: CGPoint(x: size.width - 13, y: y))
                context.stroke(path, with: .foreground, lineWidth: 1)
                if index > 0 {
                    context.draw(Text("\(index)").font(.system(size: 9, design: .monospaced)), at: CGPoint(x: 8, y: y + 8), anchor: .center)
                }
                index += 1
                y = CGFloat(index) * spacing
            }
        }
        .background(.thinMaterial)
    }
}
