// Editing tools available on the direct-manipulation TikZ canvas.

enum TikZCanvasTool: Hashable {
    case select
    case rectangle
    case ellipse
    case straightConnector
    case curveConnector
    case polylineConnector

    var nodeShape: TikZNodeShape? {
        switch self {
        case .rectangle:
            return .rectangle
        case .ellipse:
            return .ellipse
        case .select,
             .straightConnector,
             .curveConnector,
             .polylineConnector:
            return nil
        }
    }

    var connectorKind: TikZConnectorKind? {
        switch self {
        case .straightConnector:
            return .straight
        case .curveConnector:
            return .curve
        case .polylineConnector:
            return .polyline
        case .select, .rectangle, .ellipse:
            return nil
        }
    }
}
