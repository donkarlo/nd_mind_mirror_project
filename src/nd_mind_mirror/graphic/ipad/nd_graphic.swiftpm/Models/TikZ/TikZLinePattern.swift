// Supported connector stroke patterns.

enum TikZLinePattern: String, CaseIterable, Identifiable, Codable {
    case solid
    case dashed

    var id: String { rawValue }
    var title: String { rawValue.capitalized }
}
