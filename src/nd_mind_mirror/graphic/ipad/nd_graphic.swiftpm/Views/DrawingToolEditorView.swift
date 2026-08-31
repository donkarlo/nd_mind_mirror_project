import SwiftUI

/// Popover editor shared by pencil, marker, and eraser presets.
struct DrawingToolEditorView: View {
    let savedTool: SavedDrawingTool
    @Binding var color: Color
    @Binding var width: Double
    @Binding var opacity: Double
    @Binding var eraserMode: EraserMode
    let recentColorHexes: [String]
    let onRecentColor: (String) -> Void
    let onAdd: () -> Void
    let onChange: () -> Void
    let onDelete: () -> Void
    let onDone: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Text(title).font(.headline)
                Spacer()
                Button("Done", action: onDone).buttonStyle(.bordered)
            }

            if savedTool.kind == .eraser {
                eraserControls
            } else {
                inkControls
            }

            HStack {
                Button("Add after current", action: onAdd).buttonStyle(.borderedProminent)
                Button("Change current", action: onChange).buttonStyle(.bordered)
            }
            Button("Delete current tool", role: .destructive, action: onDelete)
        }
        .padding(18)
        .frame(minWidth: 400)
    }

    private var title: String {
        switch savedTool.kind {
        case .eraser: return "Eraser settings"
        case .highlighter: return "Highlighter settings"
        default: return "Pencil settings"
        }
    }

    private var eraserControls: some View {
        VStack(alignment: .leading, spacing: 12) {
            Picker("Mode", selection: $eraserMode) {
                ForEach(EraserMode.allCases) { mode in
                    Text(mode.title).tag(mode)
                }
            }
            .pickerStyle(.segmented)
            thicknessSlider(range: 2...120, step: 1, suffix: " px")
        }
    }

    private var inkControls: some View {
        VStack(alignment: .leading, spacing: 12) {
            ColorPicker("Color", selection: $color, supportsOpacity: false)
            if !recentColorHexes.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(recentColorHexes, id: \.self) { hex in
                            Button {
                                color = Color(hex: hex)
                                onRecentColor(hex)
                            } label: {
                                Circle()
                                    .fill(Color(hex: hex))
                                    .frame(width: 30, height: 30)
                                    .overlay(Circle().stroke(Color.secondary.opacity(0.3), lineWidth: 1))
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
            }
            thicknessSlider(range: 0.5...60, step: 0.5, suffix: "")
            HStack {
                Text("Opacity")
                Slider(value: $opacity, in: 0.05...1, step: 0.05)
                Text("\(Int((opacity * 100).rounded()))%")
                    .monospacedDigit().frame(width: 44)
            }
        }
    }

    private func thicknessSlider(
        range: ClosedRange<Double>,
        step: Double,
        suffix: String
    ) -> some View {
        HStack {
            Text("Thickness")
            Slider(value: $width, in: range, step: step)
            Text(width.formatted(.number.precision(.fractionLength(0...1))) + suffix)
                .monospacedDigit().frame(width: 62)
        }
    }
}
