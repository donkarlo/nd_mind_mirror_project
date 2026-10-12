// Supported directed connector arrow-head styles.

enum TikZArrowHeadStyle: String, CaseIterable, Identifiable, Codable {
    case filled
    case open

    var id: String { rawValue }

    var title: String {
        switch self {
        case .filled:
            return "Filled"
        case .open:
            return "Empty"
        }
    }
}
