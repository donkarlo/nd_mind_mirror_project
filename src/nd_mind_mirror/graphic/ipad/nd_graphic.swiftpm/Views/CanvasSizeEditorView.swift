import SwiftUI

/// Edits logical raster dimensions without remote refresh replacing draft text.
struct CanvasSizeEditorView: View {
    @Binding var widthText: String
    @Binding var heightText: String
    let onApply: () -> Void
    let onCancel: () -> Void

    var body: some View {
        NavigationStack {
            Form {
                TextField("Width", text: $widthText).keyboardType(.asciiCapableNumberPad)
                TextField("Height", text: $heightText).keyboardType(.asciiCapableNumberPad)
            }
            .navigationTitle("Canvas Size")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel", action: onCancel)
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Apply", action: onApply)
                }
            }
        }
        .frame(minWidth: 420, minHeight: 300)
    }
}
