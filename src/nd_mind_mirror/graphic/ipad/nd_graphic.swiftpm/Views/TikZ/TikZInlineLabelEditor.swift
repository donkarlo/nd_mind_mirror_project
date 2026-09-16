// Inline label editor used directly inside a TikZ node or on a connector.

import SwiftUI

struct TikZInlineLabelEditor: View {
    @Binding var text: String

    let textColor: Color
    let font: Font
    let width: CGFloat
    let height: CGFloat
    let backgroundColor: Color
    let onCommit: () -> Void

    @FocusState private var focused: Bool
    @State private var committed = false

    var body: some View {
        TextField("", text: $text)
            .textFieldStyle(.plain)
            .font(font)
            .foregroundStyle(textColor)
            .multilineTextAlignment(.center)
            .padding(.horizontal, 4)
            .frame(
                width: max(width, 36),
                height: max(height, 26)
            )
            .background(backgroundColor)
            .clipShape(
                RoundedRectangle(
                    cornerRadius: 4,
                    style: .continuous
                )
            )
            .focused($focused)
            .submitLabel(.done)
            .onSubmit(commitOnce)
            .onChange(of: focused) { _, isFocused in
                if !isFocused {
                    commitOnce()
                }
            }
            .onAppear {
                DispatchQueue.main.async {
                    focused = true
                }
            }
    }

    private func commitOnce() {
        guard !committed else {
            return
        }
        committed = true
        focused = false
        onCommit()
    }
}
