// Editing tools available on the direct-manipulation TikZ canvas.

enum TikZCanvasTool: Hashable {
    case select
    case rectangle
    case ellipse
    case connector

    var nodeShape: TikZNodeShape? {
        switch self {
        case .rectangle: return .rectangle
        case .ellipse: return .ellipse
        case .select, .connector: return nil
        }
    }
}
