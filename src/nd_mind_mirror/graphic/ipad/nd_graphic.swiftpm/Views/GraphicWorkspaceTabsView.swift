// Compact workspace switch that keeps the existing Image editor isolated from TikZ editing.

import SwiftUI

struct GraphicWorkspaceTabsView: View {
    private enum Workspace: String, CaseIterable, Identifiable {
        case image = "Image"
        case tikz = "TikZ"

        var id: String { rawValue }
    }

    @State private var workspace: Workspace = .image
    @StateObject private var tikzBridge = TikZBridgeClient()

    var body: some View {
        ZStack(alignment: .topTrailing) {
            Group {
                switch workspace {
                case .image:
                    ContentView()
                case .tikz:
                    TikZWorkspaceView(bridge: tikzBridge)
                }
            }

            Picker("Graphic workspace", selection: $workspace) {
                Label("Image", systemImage: "photo").tag(Workspace.image)
                Label("TikZ", systemImage: "point.3.connected.trianglepath.dotted").tag(Workspace.tikz)
            }
            .pickerStyle(.segmented)
            .controlSize(.mini)
            .font(.caption2)
            .frame(width: 112)
            .padding(.top, 13)
            .padding(.trailing, 62)
            .zIndex(20)
        }
        .onAppear {
            tikzBridge.connect()
        }
        .onChange(of: tikzBridge.desktopOpenToken) { _, _ in
            workspace = .tikz
        }
    }
}
