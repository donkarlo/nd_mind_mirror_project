// Presents iPad drawing and Ubuntu synchronization settings in one sheet.

import SwiftUI

struct LiveGraphicSyncSettingsView: View {
    @ObservedObject var settingsStore: LiveGraphicSyncSettingsStore
    @ObservedObject var pencilContactPreviewSettings: PencilContactPreviewSettingsStore
    @Environment(\.dismiss) private var dismiss
    @State private var updateRateHz: Double
    @State private var minimumIdleSeconds: Double

    init(
        settingsStore: LiveGraphicSyncSettingsStore,
        pencilContactPreviewSettings: PencilContactPreviewSettingsStore
    ) {
        self.settingsStore = settingsStore
        self.pencilContactPreviewSettings = pencilContactPreviewSettings
        _updateRateHz = State(initialValue: settingsStore.updateRateHz)
        _minimumIdleSeconds = State(
            initialValue: pencilContactPreviewSettings.minimumIdleSeconds
        )
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Pencil tool preview") {
                    HStack {
                        Text("Minimum idle time")
                        Spacer()
                        Text(minimumIdleSeconds.formatted(.number.precision(.fractionLength(1))) + " s")
                            .monospacedDigit()
                            .foregroundStyle(.secondary)
                    }

                    Slider(
                        value: $minimumIdleSeconds,
                        in: PencilContactPreviewSettingsStore.minimumIdleSeconds
                            ... PencilContactPreviewSettingsStore.maximumIdleSeconds,
                        step: PencilContactPreviewSettingsStore.idleStepSeconds
                    )

                    Text("The active-tool icon appears only when the Pencil has not drawn for at least this long.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

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
                        in: LiveGraphicSyncSettingsStore.minimumUpdateRateHz
                            ... LiveGraphicSyncSettingsStore.maximumUpdateRateHz,
                        step: 1
                    )

                    Text("Higher values make Ubuntu Source and Visual react faster, but use more CPU and network bandwidth.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
            .navigationTitle("iPad Settings")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Close") {
                        settingsStore.save(updateRateHz: updateRateHz)
                        pencilContactPreviewSettings.save(
                            minimumIdleSeconds: minimumIdleSeconds
                        )
                        dismiss()
                    }
                }
            }
        }
        .interactiveDismissDisabled()
    }
}
