import SwiftUI

@main
struct NDTikZSketchApp: App {
    @StateObject private var bridge = BridgeClient()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(bridge)
        }
    }
}
