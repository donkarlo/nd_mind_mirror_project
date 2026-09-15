// Connector routing modes supported by the direct TikZ editor.

enum TikZConnectorKind: String, CaseIterable, Identifiable, Hashable {
    case straight
    case curve
    case polyline

    var id: String { rawValue }

    var title: String {
        switch self {
        case .straight: return "Straight"
        case .curve: return "Curve"
        case .polyline: return "Polyline"
        }
    }
}
