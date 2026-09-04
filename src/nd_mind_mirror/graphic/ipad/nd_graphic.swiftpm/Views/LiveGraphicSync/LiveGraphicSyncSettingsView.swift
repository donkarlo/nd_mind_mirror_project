// Presents expandable iPad-to-Ubuntu synchronization settings in a dedicated sheet.

import SwiftUI

struct LiveGraphicSyncSettingsView: View {
    @ObservedObject var settingsStore: LiveGraphicSyncSettingsStore
    @Environment(\.dismiss) private var dismiss
    @State private var updateRateHz: Double

    init(settingsStore: LiveGraphicSyncSettingsStore) {
        self.settingsStore = settingsStore
        _updateRateHz = State(initialValue: settingsStore.updateRateHz)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Live Ubuntu update") {
                    HStack {
                        Text("Update rate")
                        Spacer()
                        Text("\(Int(updateRateHz.rounded())) updates/s")
                            .monospacedDigit()
                            .foregroundStyle(.secondary)
                    }

                    Slider(
                        value: $updateRateHz,
                        in: LiveGraphicSyncSettingsStore.minimumUpdateRateHz ... LiveGraphicSyncSettingsStore.maximumUpdateRateHz,
                        step: 1
                    )

                    Text("Higher values make Ubuntu Source and Visual react faster, but use more CPU and network bandwidth.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
            .navigationTitle("iPad → Ubuntu")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Close") {
                        settingsStore.save(updateRateHz: updateRateHz)
                        dismiss()
                    }
                }
            }
        }
        .interactiveDismissDisabled()
    }
}
