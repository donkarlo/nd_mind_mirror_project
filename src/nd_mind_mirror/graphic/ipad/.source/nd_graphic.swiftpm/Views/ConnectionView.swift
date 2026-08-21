import SwiftUI

struct ConnectionView: View {
    @EnvironmentObject private var bridge: GraphicBridgeClient
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Form {
                Section("iPad listener") {
                    LabeledContent("TCP port", value: "8768")
                    SecureField("Token (optional)", text: $bridge.token)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                }
                Section {
                    Button("Start listening for Ubuntu") {
                        bridge.connect()
                        dismiss()
                    }
                } footer: {
                    Text("Run nd_graphic_bridge on Ubuntu. Ubuntu discovers this iPad on the LAN and opens the TCP connection to it; the iPad does not initiate a local-network connection.")
                }
            }
            .navigationTitle("Connection")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close") { dismiss() }
                }
            }
        }
    }
}
