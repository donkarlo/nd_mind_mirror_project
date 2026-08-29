import Foundation

/// Defines whether an eraser removes only touched stroke pixels or the entire touched stroke.
enum EraserMode: String, Codable, CaseIterable, Identifiable {
    case partial
    case whole

    var id: String { rawValue }

    var title: String {
        switch self {
        case .partial: return "Partial"
        case .whole: return "Whole"
        }
    }
}
