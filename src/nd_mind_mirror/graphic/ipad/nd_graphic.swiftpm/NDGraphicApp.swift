import SwiftUI

@main
struct NDGraphicApp: App {
    var body: some Scene {
        WindowGroup {
            NDGraphicBootstrapView()
        }
    }
}

/// The first screen intentionally has no PencilKit, URLSession, UserDefaults,
/// or bridge object. Swift Playgrounds must render this screen before any of
/// the graphic stack is initialized. This also makes a stale/cached package
/// obvious because the version is printed in the UI.
struct NDGraphicBootstrapView: View {
    @State private var openWorkspace = false

    var body: some View {
        ZStack {
            Color.indigo
                .ignoresSafeArea()

            if openWorkspace {
                ContentView()
                    .background(Color.white)
            } else {
                VStack(spacing: 24) {
                    Image(systemName: "brain.head.profile")
                        .font(.system(size: 76, weight: .semibold))
                    Text("ND Graphic 0.30")
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
