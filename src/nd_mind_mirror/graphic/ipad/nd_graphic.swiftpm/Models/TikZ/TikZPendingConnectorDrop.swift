// Deferred blank-canvas connector endpoint awaiting the user's target-shape choice.

import CoreGraphics

struct TikZPendingConnectorDrop {
    let sourceNodeName: String
    let point: CGPoint
}
