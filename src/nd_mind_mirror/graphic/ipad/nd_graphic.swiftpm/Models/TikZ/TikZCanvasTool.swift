// Editing tools available on the direct-manipulation TikZ canvas.

enum TikZCanvasTool: String, Hashable, Codable {
    case select
    case rectangle
    case ellipse
    case triangle
    case straightConnector
    case curveConnector
    case polylineConnector

    var nodeShape: TikZNodeShape? {
        switch self {
        case .rectangle:
            return .rectangle
        case .ellipse:
            return .ellipse
        case .triangle:
            return .triangle
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
        case .select, .rectangle, .ellipse, .triangle:
            return nil
        }
    }
}
