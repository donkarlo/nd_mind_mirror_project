// Inline TikZ element properties using native SwiftUI color pickers.

import Foundation
import SwiftUI

struct TikZStyleToolbarView: View {
    enum Mode: Equatable {
        case hidden
        case node
        case edge
    }

    let mode: Mode
    @Binding var nodeStyle: TikZNodeStyle
    @Binding var edgeStyle: TikZEdgeStyle
    @Binding var label: String
    let labelPlaceholder: String
    let onCommitLabel: (() -> Void)?

    var body: some View {
        Group {
            switch mode {
            case .hidden:
                EmptyView()
            case .node:
                HStack(spacing: 12) {
                    labelField
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
                    lineWidthSlider(value: $nodeStyle.lineWidth)
                    Spacer(minLength: 0)
                }
                .propertyRowBackground()
            case .edge:
                HStack(spacing: 12) {
                    labelField
                    nativeColorPicker(
                        "Line",
                        value: $edgeStyle.strokeColor
                    )
                    nativeColorPicker(
                        "Text",
                        value: $edgeStyle.textColor
                    )
                    lineWidthSlider(value: $edgeStyle.lineWidth)
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
                .propertyRowBackground()
            }
        }
    }

    private var labelField: some View {
        TextField(
            labelPlaceholder,
            text: $label
        )
        .textFieldStyle(.roundedBorder)
        .frame(maxWidth: 190)
        .onSubmit {
            onCommitLabel?()
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
    }
}

private extension View {
    func propertyRowBackground() -> some View {
        self
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(
                Color(
                    uiColor: .secondarySystemBackground
                )
            )
    }
}
