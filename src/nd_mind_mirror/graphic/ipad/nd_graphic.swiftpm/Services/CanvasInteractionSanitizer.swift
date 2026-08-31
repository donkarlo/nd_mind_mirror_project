import UIKit

/// Removes PencilKit's built-in edit/context menus while preserving drawing and navigation gestures.
@MainActor
final class CanvasInteractionSanitizer {
    static func suppressMenus(in rootView: UIView) {
        removeMenuInteractions(from: rootView)
        for subview in rootView.subviews {
            suppressMenus(in: subview)
        }
    }

    static func disableLegacyTwoFingerSingleTap(in view: UIView) {
        for case let tap as UITapGestureRecognizer in view.gestureRecognizers ?? []
        where tap.numberOfTouchesRequired == 2 && tap.numberOfTapsRequired == 1 {
            tap.isEnabled = false
        }
    }

    private static func removeMenuInteractions(from view: UIView) {
        for interaction in view.interactions {
            if interaction is UIEditMenuInteraction || interaction is UIContextMenuInteraction {
                view.removeInteraction(interaction)
            }
        }

        for case let longPress as UILongPressGestureRecognizer in view.gestureRecognizers ?? [] {
            longPress.isEnabled = false
        }
    }
}
