// Semantic canvas hit target used by the centralized iPad interaction layer.

import Foundation

enum TikZCanvasHitTarget: Equatable {
    case node(String)
    case edge(String)
}
