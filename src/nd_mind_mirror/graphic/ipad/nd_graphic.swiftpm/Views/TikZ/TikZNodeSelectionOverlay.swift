// Eight resize handles plus one separate move handle for a selected TikZ node.

import SwiftUI

struct TikZNodeSelectionOverlay: View {
    let node: TikZNode
    let canvasSize: CGSize
    let onMove: (CGPoint) -> Void
    let onResize: (CGPoint, CGSize) -> Void

    @State private var activeHandle: TikZResizeHandle?
    @State private var resizeTranslation: CGSize = .zero
    @State private var moveTranslation: CGSize = .zero
    @State private var moving = false

    private let geometry = TikZNodeGeometry()
    private let mapper = TikZCoordinateMapper()
    private let handleDiameter: CGFloat = 14
    private let moveHandleDiameter: CGFloat = 24
    private let minimumWidth: CGFloat = 36
    private let minimumHeight: CGFloat = 28

    var body: some View {
        let baseRect = geometry.rect(for: node, in: canvasSize)
        let movedBase = baseRect.offsetBy(
            dx: moveTranslation.width,
            dy: moveTranslation.height
        )
        let displayedRect = resizedRect(
            base: movedBase,
            handle: activeHandle,
            translation: resizeTranslation
        )

        ZStack {
            Rectangle()
                .stroke(
                    Color.accentColor,
                    style: StrokeStyle(lineWidth: 1.5, dash: [5, 4])
                )
                .frame(width: displayedRect.width, height: displayedRect.height)
                .position(x: displayedRect.midX, y: displayedRect.midY)
                .allowsHitTesting(false)

            ForEach(TikZResizeHandle.allCases) { handle in
                Circle()
                    .fill(Color.white)
                    .overlay(Circle().stroke(Color.accentColor, lineWidth: 2))
                    .frame(width: handleDiameter, height: handleDiameter)
                    .contentShape(Circle().inset(by: -8))
                    .position(handle.point(in: displayedRect))
                    .gesture(resizeGesture(handle: handle, baseRect: movedBase))
            }

            ZStack {
                Circle().fill(Color.accentColor)
                Image(systemName: "arrow.up.and.down.and.arrow.left.and.right")
                    .font(.system(size: 10, weight: .bold))
                    .foregroundStyle(.white)
            }
            .frame(width: moveHandleDiameter, height: moveHandleDiameter)
            .contentShape(Circle().inset(by: -8))
            .position(
                x: displayedRect.midX,
                y: max(displayedRect.minY - 24, moveHandleDiameter / 2)
            )
            .gesture(moveGesture(baseRect: baseRect))
            .accessibilityLabel("Move selected TikZ shape")
        }
        .frame(width: canvasSize.width, height: canvasSize.height)
        .onChange(of: node.id) { _, _ in resetTransientState() }
    }

    private func moveGesture(baseRect: CGRect) -> some Gesture {
        DragGesture(minimumDistance: 1)
            .onChanged { value in
                moving = true
                moveTranslation = boundedMove(value.translation, baseRect: baseRect)
            }
            .onEnded { value in
                let translation = boundedMove(value.translation, baseRect: baseRect)
                let rect = baseRect.offsetBy(dx: translation.width, dy: translation.height)
                resetTransientState()
                onMove(
                    mapper.tikzPoint(
                        for: CGPoint(x: rect.midX, y: rect.midY),
                        in: canvasSize
                    )
                )
            }
    }

    private func resizeGesture(handle: TikZResizeHandle, baseRect: CGRect) -> some Gesture {
        DragGesture(minimumDistance: 1)
            .onChanged { value in
                guard !moving else { return }
                activeHandle = handle
                resizeTranslation = value.translation
            }
            .onEnded { value in
                guard !moving else { return }
                let finalRect = resizedRect(
                    base: baseRect,
                    handle: handle,
                    translation: value.translation
                )
                activeHandle = nil
                resizeTranslation = .zero
                commitResize(finalRect)
            }
    }

    private func boundedMove(_ translation: CGSize, baseRect: CGRect) -> CGSize {
        let minimumX = -baseRect.minX
        let maximumX = canvasSize.width - baseRect.maxX
        let minimumY = -baseRect.minY
        let maximumY = canvasSize.height - baseRect.maxY
        return CGSize(
            width: min(max(translation.width, minimumX), maximumX),
            height: min(max(translation.height, minimumY), maximumY)
        )
    }

    private func resizedRect(
        base: CGRect,
        handle: TikZResizeHandle?,
        translation: CGSize
    ) -> CGRect {
        guard let handle else { return base }
        var left = base.minX
        var right = base.maxX
        var top = base.minY
        var bottom = base.maxY
        if handle.movesLeft { left += translation.width }
        if handle.movesRight { right += translation.width }
        if handle.movesTop { top += translation.height }
        if handle.movesBottom { bottom += translation.height }
        if right - left < minimumWidth {
            if handle.movesLeft { left = right - minimumWidth } else { right = left + minimumWidth }
        }
        if bottom - top < minimumHeight {
            if handle.movesTop { top = bottom - minimumHeight } else { bottom = top + minimumHeight }
        }
        left = max(left, 0)
        top = max(top, 0)
        right = min(right, canvasSize.width)
        bottom = min(bottom, canvasSize.height)
        return CGRect(
            x: left,
            y: top,
            width: max(right - left, minimumWidth),
            height: max(bottom - top, minimumHeight)
        )
    }

    private func commitResize(_ rect: CGRect) {
        let center = mapper.tikzPoint(
            for: CGPoint(x: rect.midX, y: rect.midY),
            in: canvasSize
        )
        let topLeft = mapper.tikzPoint(for: CGPoint(x: rect.minX, y: rect.minY), in: canvasSize)
        let bottomRight = mapper.tikzPoint(for: CGPoint(x: rect.maxX, y: rect.maxY), in: canvasSize)
        onResize(
            center,
            CGSize(
                width: abs(bottomRight.x - topLeft.x),
                height: abs(bottomRight.y - topLeft.y)
            )
        )
    }

    private func resetTransientState() {
        activeHandle = nil
        resizeTranslation = .zero
        moveTranslation = .zero
        moving = false
    }
}
