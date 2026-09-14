// Keep the raster bridge session alive while presenting exactly one interactive workspace.

import SwiftUI

struct GraphicWorkspaceRouterView: View {
    @ObservedObject private var router = GraphicEditorSessionRouter.shared

    var body: some View {
        ZStack {
            // ContentView owns the long-lived GraphicBridgeClient. Keeping this view in
            // the hierarchy prevents Image↔TikZ navigation from destroying the TCP listener.
            ContentView()
                .opacity(router.workspace == .image ? 1 : 0)
                .allowsHitTesting(router.workspace == .image)
                .accessibilityHidden(router.workspace != .image)
                .zIndex(0)

            if router.workspace == .tikz {
                TikZWorkspaceView(router: router)
                    .background(Color(uiColor: .systemBackground))
                    .zIndex(1)
            }
        }
    }
}
