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

struct NDGraphicBootstrapView: View {
    @State private var openWorkspace = false

    private var displayVersion: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "unknown"
    }

    var body: some View {
        ZStack {
            Color.indigo
                .ignoresSafeArea()

            if openWorkspace {
                ContentView()
                    .background(Color.white)
            } else {
                VStack(spacing: 22) {
                    Image(systemName: "brain.head.profile")
                        .font(.system(size: 76, weight: .semibold))
                    Text("MIGRATION 4 BUILD")
                        .font(.system(size: 30, weight: .black))
                    Text("ND Graphic M4 \(displayVersion)")
                        .font(.system(size: 36, weight: .bold))
                    Text("Bundle: com.nd.mindmirror.graphic.m4")
                        .font(.system(.body, design: .monospaced))
                    Text("Mind Mirror iPad graphic editor")
                        .font(.title3)
                    Button("Open Migration 4 Editor") {
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
