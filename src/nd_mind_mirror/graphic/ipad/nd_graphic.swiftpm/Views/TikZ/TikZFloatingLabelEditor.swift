// Floating label editor that stays above the canvas instead of changing canvas layout.

import SwiftUI

struct TikZFloatingLabelEditor: View {
    @Binding var text: String
    let title: String
    let onCommit: () -> Void

    @FocusState private var focused: Bool

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: "character.cursor.ibeam")
                .foregroundStyle(Color.accentColor)

            Text(title)
                .font(.caption.bold())
                .foregroundStyle(.secondary)
                .lineLimit(1)

            TextField("Label", text: $text)
                .textFieldStyle(.roundedBorder)
                .focused($focused)
                .submitLabel(.done)
                .onSubmit(commit)

            Button(action: commit) {
                Image(systemName: "checkmark.circle.fill")
                    .font(.title3)
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Commit label")
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .frame(maxWidth: 560)
        .background(
            .ultraThinMaterial,
            in: RoundedRectangle(
                cornerRadius: 12,
                style: .continuous
            )
        )
        .overlay(
            RoundedRectangle(
                cornerRadius: 12,
                style: .continuous
            )
            .stroke(Color.secondary.opacity(0.25), lineWidth: 1)
        )
        .shadow(radius: 7, y: 3)
        .onAppear {
            DispatchQueue.main.async {
                focused = true
            }
        }
    }

    private func commit() {
        focused = false
        onCommit()
    }
}
