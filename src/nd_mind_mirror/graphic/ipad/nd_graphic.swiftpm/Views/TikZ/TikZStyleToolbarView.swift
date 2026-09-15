// Fixed-height TikZ element properties using native SwiftUI controls.

import Foundation
import SwiftUI

struct TikZStyleToolbarView: View {
    enum Mode: Equatable {
        case node
        case edge
    }

    let mode: Mode
    @Binding var nodeStyle: TikZNodeStyle
    @Binding var edgeStyle: TikZEdgeStyle

    private let toolbarHeight: CGFloat = 48

    var body: some View {
        ScrollView(
            .horizontal,
            showsIndicators: false
        ) {
            Group {
                switch mode {
                case .node:
                    nodeControls
                case .edge:
                    edgeControls
                }
            }
            .padding(.horizontal, 8)
            .frame(height: toolbarHeight)
        }
        .frame(height: toolbarHeight)
        .background(
            Color(
                uiColor: .secondarySystemBackground
            )
        )
    }

    private var nodeControls: some View {
        HStack(spacing: 12) {
            nativeColorPicker(
                "Fill",
                value: $nodeStyle.fillColor
            )
            nativeColorPicker(
                "Border",
                value: $nodeStyle.strokeColor
            )
            nativeColorPicker(
                "Text",
                value: $nodeStyle.textColor
            )
            lineWidthSlider(
                value: $nodeStyle.lineWidth
            )
            Spacer(minLength: 0)
        }
    }

    private var edgeControls: some View {
        HStack(spacing: 12) {
            nativeColorPicker(
                "Line",
                value: $edgeStyle.strokeColor
            )
            nativeColorPicker(
                "Text",
                value: $edgeStyle.textColor
            )
            lineWidthSlider(
                value: $edgeStyle.lineWidth
            )
            linePatternPicker
            Toggle(
                "Arrow",
                isOn: $edgeStyle.directed
            )
            .toggleStyle(.switch)
            .fixedSize()
            if edgeStyle.directed {
                arrowHeadPicker
            }
            Spacer(minLength: 0)
        }
    }

    private var linePatternPicker: some View {
        Picker(
            "Stroke",
            selection: $edgeStyle.linePattern
        ) {
            ForEach(TikZLinePattern.allCases) { pattern in
                Text(pattern.title).tag(pattern)
            }
        }
        .pickerStyle(.segmented)
        .frame(width: 150)
    }

    private var arrowHeadPicker: some View {
        Picker(
            "Head",
            selection: $edgeStyle.arrowHeadStyle
        ) {
            ForEach(TikZArrowHeadStyle.allCases) { style in
                Text(style.title).tag(style)
            }
        }
        .pickerStyle(.segmented)
        .frame(width: 150)
    }

    private func nativeColorPicker(
        _ title: String,
        value: Binding<TikZColorValue>
    ) -> some View {
        ColorPicker(
            title,
            selection: Binding(
                get: {
                    value.wrappedValue.color
                },
                set: {
                    value.wrappedValue = TikZColorValue(
                        color: $0
                    )
                }
            ),
            supportsOpacity: false
        )
        .font(.caption)
        .fixedSize()
    }

    private func lineWidthSlider(
        value: Binding<Double>
    ) -> some View {
        HStack(spacing: 6) {
            Text("Width")
                .font(.caption)
                .foregroundStyle(.secondary)
            Slider(
                value: value,
                in: 0.5...4.0,
                step: 0.25
            )
            .frame(width: 100)
            Text(
                String(
                    format: "%.2g",
                    value.wrappedValue
                )
            )
            .font(.caption2.monospacedDigit())
            .frame(
                width: 30,
                alignment: .trailing
            )
        }
        .fixedSize(horizontal: false, vertical: true)
    }
}
