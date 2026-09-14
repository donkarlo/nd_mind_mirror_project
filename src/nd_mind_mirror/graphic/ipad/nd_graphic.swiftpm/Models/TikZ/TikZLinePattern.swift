// Supported connector stroke patterns.

enum TikZLinePattern: String, CaseIterable, Identifiable {
    case solid
    case dashed

    var id: String { rawValue }
    var title: String { rawValue.capitalized }
}
