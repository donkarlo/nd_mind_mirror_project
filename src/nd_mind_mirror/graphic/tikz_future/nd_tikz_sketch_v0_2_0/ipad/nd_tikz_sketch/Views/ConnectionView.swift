import SwiftUI

struct ConnectionView: View {
    @EnvironmentObject private var bridge: BridgeClient
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Form {
                Section("Ubuntu TikZ bridge") {
                    TextField("ws://ubuntu.local:8765/ws", text: $bridge.serverURL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .keyboardType(.URL)
                    SecureField("Optional shared token", text: $bridge.token)
                }
                Section {
                    Text("The Ubuntu bridge should point at the same workspace that Dropbox syncs. WebSocket is the live path; Dropbox remains the persistent file sync layer.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Connection")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(bridge.isConnected ? "Reconnect" : "Connect") {
                        bridge.connect()
                        dismiss()
                    }
                }
            }
        }
    }
}
