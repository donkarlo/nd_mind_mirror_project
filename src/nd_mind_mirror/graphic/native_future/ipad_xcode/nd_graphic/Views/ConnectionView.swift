import SwiftUI

struct ConnectionView: View {
    @EnvironmentObject private var bridge: GraphicBridgeClient
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Form {
                Section("Ubuntu bridge") {
                    TextField("ws://192.168.1.2:8766/ws", text: $bridge.endpoint)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .keyboardType(.URL)
                    SecureField("Token (optional)", text: $bridge.token)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                }
                Section {
                    Button("Connect") {
                        bridge.connect()
                        dismiss()
                    }
                    .disabled(bridge.endpoint.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                } footer: {
                    Text("Run nd_graphic_bridge on Ubuntu, then use Ubuntu's LAN IP address here. Both devices must be on the same network.")
                }
            }
            .navigationTitle("Connection")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
    }
}
