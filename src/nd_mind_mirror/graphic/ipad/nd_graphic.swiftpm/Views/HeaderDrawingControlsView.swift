import SwiftUI

/// Places document-wide drawing controls in the main header.
struct HeaderDrawingControlsView: View {
    @Binding var showMeasurementRulers: Bool
    @Binding var showMeasurementGrid: Bool

    let onZoom100: () -> Void
    let onSetCanvas: (Double, Double) -> Void
    let onCustomCanvas: () -> Void
    let onClearDrawing: () -> Void
    let onDisconnect: () -> Void

    var body: some View {
        HStack(spacing: 2) {
            toggleButton(
                value: $showMeasurementRulers,
                image: "ruler",
                label: "Rulers"
            )

            toggleButton(
                value: $showMeasurementGrid,
                image: "square.grid.3x3",
                label: "Grid"
            )

            canvasMenu
        }
    }

    private func toggleButton(
        value: Binding<Bool>,
        image: String,
        label: String
    ) -> some View {
        Button {
            value.wrappedValue.toggle()
        } label: {
            Image(systemName: image)
                .font(.title3)
                .frame(width: 38, height: 44)
                .foregroundStyle(value.wrappedValue ? Color.accentColor : Color.primary)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(label)
    }

    private var canvasMenu: some View {
        Menu {
            Button("100% zoom", action: onZoom100)
            Divider()
            Button("A4 portrait — 1240 × 1754") { onSetCanvas(1240, 1754) }
            Button("A4 landscape — 1754 × 1240") { onSetCanvas(1754, 1240) }
            Button("Square — 1600 × 1600") { onSetCanvas(1600, 1600) }
            Button("Custom canvas size…", action: onCustomCanvas)
            Divider()
            Button("Clear drawing", role: .destructive, action: onClearDrawing)
            Button("Disconnect", role: .destructive, action: onDisconnect)
        } label: {
            Image(systemName: "ellipsis.circle")
                .font(.title3)
                .frame(width: 38, height: 44)
                .contentShape(Rectangle())
        }
        .accessibilityLabel("Canvas options")
    }
}
