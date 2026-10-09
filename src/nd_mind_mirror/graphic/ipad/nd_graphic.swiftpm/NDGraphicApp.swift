// Bootstrap the Mind Mirror iPad companion before opening the shared graphic workspace.

import Foundation
import SwiftUI

@main
struct NDGraphicApp: App {
    var body: some Scene {
        WindowGroup {
            NDGraphicBootstrapView()
        }
    }
}

/// Swift Playgrounds renders a lightweight bootstrap before the bridge/editor stack.
struct NDGraphicBootstrapView: View {
    @State private var openWorkspace = false

    private var displayVersion: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "unknown"
    }

    var body: some View {
        ZStack {
            // The opened editor must not retain the indigo launch-screen
            // background in the system status-bar safe area.
            (openWorkspace ? Color(uiColor: .systemBackground) : Color.indigo)
                .ignoresSafeArea()

            if openWorkspace {
                GraphicWorkspaceRouterView()
            } else {
                VStack(spacing: 24) {
                    Image(systemName: "brain.head.profile")
                        .font(.system(size: 76, weight: .semibold))
                    Text("ND Graphic \(displayVersion)")
                        .font(.system(size: 38, weight: .bold))
                    Text("Mind Mirror iPad graphic editor")
                        .font(.title3)
                    Button("Open graphic editor") {
                        openWorkspace = true
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                    .tint(.white)
                    .foregroundStyle(.indigo)
                }
                .foregroundStyle(.white)
                .padding(40)
            }
        }
    }
}
